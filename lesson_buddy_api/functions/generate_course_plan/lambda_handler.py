import json
import boto3
from urllib import request, parse
import base64
import uuid
import os
import datetime
from botocore.exceptions import ClientError # For DynamoDB error handling
from urllib import error as urllib_error # For call_model HTTP errors

def lambda_handler(event, context):
    try:
        print(event)
        if event['isBase64Encoded']:
            decoded = base64.b64decode(event['body']).decode('utf-8')
            data = dict(parse.parse_qsl(decoded))
        else:
            data = json.loads(event['body'])
        topic = data.get('topic','No topic provided')
        timeline = data.get('timeline', '2 months')
        difficulty = data.get('difficulty','easy')
        custom_instructions = data.get('custom_instructions', None)
        # user_id = data.get('user_id', None) # User ID will be extracted from the auth token

        # Extract User ID from the Authorization header
        try:
            auth_header = event.get('headers', {}).get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return {
                    'statusCode': 401,
                    'body': json.dumps({'error': 'Missing or malformed Authorization header'})
                }
            
            token = auth_header.split(' ')[1]
            payload_b64 = token.split('.')[1]
            payload_b64 += '=' * (-len(payload_b64) % 4)
            decoded_payload = base64.b64decode(payload_b64).decode('utf-8')
            payload_json = json.loads(decoded_payload)
            user_id = payload_json.get('sub')

            if not user_id:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'User ID (sub) not found in token'}),
                    'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
                }
        except Exception as e:
            print(f"Error decoding token or extracting sub: {str(e)}")
            return {
                'statusCode': 401,
                'body': json.dumps({'error': f'Invalid token: {str(e)}'}),
                'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
            }

        try:
            course_plan_str = generate_course_plan(topic, timeline, difficulty, custom_instructions)
            if course_plan_str is None: # call_model now returns None on error
                 raise ValueError("Failed to generate course plan from LLM: Received no content.")
            course_plan = json.loads(course_plan_str) 
        except json.JSONDecodeError as e: # Catch this more specific error first
            print(f"JSONDecodeError parsing LLM output: {str(e)}")
            return {
                'statusCode': 502,
                'body': json.dumps({'error': f'Failed to parse course plan from LLM: Invalid JSON format. {str(e)}'}),
                'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
            }
        except ValueError as e: # Catch other ValueErrors, including the one raised above
            print(f"Error generating or parsing course plan: {str(e)}")
            return {
                'statusCode': 502, # Bad Gateway, as we failed to get a valid response from upstream (LLM)
                'body': json.dumps({'error': f'Failed to generate or parse course plan from LLM: {str(e)}'}),
                'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
            }
        
        course_plan['CourseID'] = str(uuid.uuid4())
        course_plan['UserID'] = user_id

        # Initialize chapter statuses
        chapters_status = {}
        timestamp = datetime.datetime.utcnow().isoformat()
        for chapter in course_plan['chapters']:
            chapter_id = chapter.get('id')
            if chapter_id: # Ensure chapter has an ID
                chapters_status[chapter_id] = {
                    'lessons_status': 'PENDING',
                    'mcqs_status': 'PENDING',
                    'last_updated': timestamp
                }
        course_plan['chapters_status'] = chapters_status

        print(course_plan)
        
        # save to dynamodb
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('COURSE_TABLE_NAME')
        # Assuming COURSE_TABLE_NAME is guaranteed by CDK as per user feedback
        table = dynamodb.Table(table_name) # type: ignore
        
        try:
            table.put_item(Item=course_plan)
            print('Saved to DynamoDB')
        except ClientError as e:
            print(f"Error saving to DynamoDB: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': f'Could not save course plan to database: {str(e)}'}),
                'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
            }

        return {
            'statusCode': 200,
            'body': json.dumps(course_plan),
            'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
        }
    except Exception as e: # Catch-all for any other unexpected errors
        print(f"Unexpected error in lambda_handler: {str(e)}")        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'An unexpected server error occurred: {str(e)}'}),
            'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
        }

def call_model(prompt, output_format=None):
    api_key = os.environ.get('API_KEY')
    if not api_key:
        # This check is important here as call_model is a standalone utility
        print("Error in call_model: API_KEY environment variable not set.")
        # Return None, lambda_handler will catch this and raise ValueError
        return None 
        
    url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
    data = {
        "model": "gemini-2.5-pro-preview-05-06",
        "messages": [{"role": "user", "content": prompt}]
        
    }
    
    if output_format:
        data['response_format'] = {
            "type": "json_schema",
            "json_schema" : {
                "name": "course_plan",
                "schema": output_format  
            }
        }

    print(data)

    data_bytes = json.dumps(data).encode('utf-8')
    
    req = request.Request(url, data=data_bytes)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Bearer {api_key}')
    
    try:
        with request.urlopen(req) as resp:
            if resp.status == 200:
                content = resp.read()
                output = json.loads(content)
                if output.get('choices') and output['choices'][0].get('message') and 'content' in output['choices'][0]['message']:
                    return output['choices'][0]['message']['content']
                else:
                    print(f"LLM response missing expected structure: {output}")
                    # Return None, lambda_handler will catch this
                    return None
            else:
                error_content = resp.read().decode('utf-8')
                print(f"LLM API HTTP Error: {resp.status} - {resp.reason}. Response: {error_content}")
                return None # Indicate failure
                
    except urllib_error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        print(f"HTTPError calling LLM: {e.code} - {e.reason}. Body: {error_body}")
        return None
    except urllib_error.URLError as e:
        print(f"URLError calling LLM: {e.reason}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSONDecodeError parsing LLM response: {e}")
        return None
    except Exception as e: 
        print(f"Unexpected error in call_model: {e}")
        return None

course_plan_schema = {
    "type": "object",
    "description": "The full course plan.",
    "properties": {
        "title" : {
            "type": "string",
            "description": "The title of the course plan."
        },
        "description": {
            "type": "string",
            "description": "The description of the course plan."
        },
        "chapters" : {
            "type": "array",
            "description": "The chapters of the course plan.",
            "items": {
                "type": "object",
                "description": "The chapter of the course plan.",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the chapter."
                    },
                    "description": {
                        "type": "string",
                        "description": "The description of the chapter."
                    },
                    "lessons": {
                        "type": "array",
                        "description": "The lessons of the chapter.",
                        "items": {
                            "type": "object",
                            "description": "The lesson of the chapter.",
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "The title of the lesson."
                                },
                                "description": {
                                    "type": "string",
                                    "description": "The description of the lesson's overall content."
                                },
                                "id": {
                                    "type": "string",
                                    "description": "A unique ID for the lesson."
                                }
                            },
                            "additionalProperties": False,
                            "required": [
                                "title",
                                "description",
                                "id"
                            ]
                        }
                    },
                    "time" : {
                        "type": "string",
                        "description": "The time required to complete the chapter."
                    },
                    "id": {
                        "type": "string",
                        "description": "A unique ID for the chapter."
                    }
                },
                "additionalProperties": False,
                "required": [
                    "title",
                    "description",
                    "lessons",
                    "time",
                    "id"
                ]
            }
        },
    },
    "additionalProperties": False,
    "required": [
        "title",
        "description",
        "chapters"
    ]
}

def generate_course_plan(topic, timeline, difficulty, custom_instructions):
    system_prompt = f"""
    You are a course assistant that helps students to create a course plan based on their topic, timeline and difficulty.
    Output a JSON object representing the course plan with the provided schema. 

    Topic: {topic}
    Timeline: {timeline}
    Difficulty: {difficulty}
    Custom Instructions: {custom_instructions}
    """
    return call_model(system_prompt, course_plan_schema)
