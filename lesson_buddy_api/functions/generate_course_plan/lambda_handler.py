import json
import boto3
from urllib import request, parse
import base64
import uuid
import os
import datetime
import random
from concurrent.futures import ThreadPoolExecutor

from botocore.exceptions import ClientError # For DynamoDB error handling
from urllib import error as urllib_error # For call_model HTTP errors

# Create a Bedrock Runtime client in the AWS Region of your choice.
bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
s3_client = boto3.client("s3")

def generate_course_image(course_title, course_id):
    """
    Generates a cover image for the course using Amazon Nova Canvas and uploads it to S3.
    Returns the S3 URL of the uploaded image.
    """
    try:
        # Set the model ID.
        model_id = "amazon.nova-canvas-v1:0"

        # Define the image generation prompt for the model.
        prompt = f"A stylized, artistic, and inviting cover image for a course titled '{course_title}'. The image should be relevant to the topic and visually appealing."

        # Generate a random seed between 0 and 858,993,459
        seed = random.randint(0, 858993460)

        # Format the request payload using the model's native structure.
        native_request = {
            "taskType": "TEXT_IMAGE",
            "textToImageParams": {"text": prompt},
            "imageGenerationConfig": {
                "seed": seed,
                "quality": "standard",
                "height": 1024,
                "width": 1024,
                "numberOfImages": 1,
            },
        }

        # Convert the native request to JSON.
        request_body = json.dumps(native_request)

        # Invoke the model with the request.
        response = bedrock_client.invoke_model(modelId=model_id, body=request_body)

        # Decode the response body.
        model_response = json.loads(response["body"].read())

        # Extract the image data.
        base64_image_data = model_response["images"][0]
        image_data = base64.b64decode(base64_image_data)

        # Upload to S3
        bucket_name = os.environ.get('COURSE_IMAGES_BUCKET_NAME')
        if not bucket_name:
            print("Error: COURSE_IMAGES_BUCKET_NAME environment variable not set.")
            return None

        # Generate a unique key for the image in S3
        s3_key = f"course-covers/{course_id}.png"

        s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=image_data, ContentType='image/png')
        print(f"Image uploaded to s3://{bucket_name}/{s3_key}")

        # Construct the public URL (assuming public read access is configured on the bucket)
        image_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
        return image_url

    except ClientError as e:
        print(f"Bedrock or S3 Client Error generating image: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error generating course image: {str(e)}")
        return None

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

        # Extract User ID from the event context
        try:
            user_id = event['requestContext']['authorizer']['claims']['sub']
            if not user_id:
                # This case should ideally not happen if the authorizer is configured correctly
                # and always includes 'sub', but good to have a fallback.
                print("User ID (sub) is missing from authorizer claims.")
                return {
                    'statusCode': 401, # Unauthorized
                    'body': json.dumps({'error': 'User ID not found in request context'}),
                    'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
                }
        except KeyError as e:
            # This handles cases where the path to 'sub' might be missing
            print(f"Error accessing user_id from event context: {str(e)}")
            return {
                'statusCode': 401, # Unauthorized
                'body': json.dumps({'error': f'Could not extract user ID from request context: {str(e)}'}),
                'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
            }
        except Exception as e: # Catch any other unexpected errors during user_id extraction
            print(f"Unexpected error extracting user_id: {str(e)}")
            return {
                'statusCode': 500, # Internal Server Error
                'body': json.dumps({'error': f'An unexpected error occurred while processing user identity: {str(e)}'}),
                'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
            }

        course_id = str(uuid.uuid4()) # Generate CourseID early for parallel image generation

        # Use ThreadPoolExecutor to run LLM call and image generation in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            llm_future = executor.submit(generate_course_plan, topic, timeline, difficulty, custom_instructions)
            image_future = executor.submit(generate_course_image, topic, course_id)

            try:
                course_plan_str = llm_future.result() # Wait for LLM result
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
            
            # Get image URL after course plan is generated
            image_url = image_future.result()
            if image_url:
                course_plan['cover_image_url'] = image_url
            else:
                print("Warning: Failed to generate or upload course cover image.")
                course_plan['cover_image_url'] = None # Or a default image URL

        # Add blank chapter_image_url to each chapter
        for chapter in course_plan['chapters']:
            chapter['chapter_image_url'] = ""

        course_plan['CourseID'] = course_id
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


def call_model(prompt, endpoint, api_key, model, tools=None):    
    if not api_key:
        # This check is important here as call_model is a standalone utility
        print("Error in call_model: API_KEY environment variable not set.")
        # Return None, lambda_handler will catch this and raise ValueError
        return None 
            
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 8192        
    }
    
    if tools:
        data['tools'] = tools

    print(data)

    data_bytes = json.dumps(data).encode('utf-8')
    
    req = request.Request(endpoint, data=data_bytes)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Bearer {api_key}')
    
    try:
        with request.urlopen(req) as resp:
            if resp.status == 200:
                content = resp.read()
                output = json.loads(content)
                if output.get('choices') and output['choices'][0].get('message') and 'content' in output['choices'][0]['message']:
                    return output['choices'][0]['message']
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
        "cover_image_url": {
            "type": ["string", "null"],
            "description": "The URL of the course cover image, or null if not available."
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

tools = [
        {
            "type": "function",
            "function": {
            "name": "generate_course_plan",
            "description": "Output a JSON object representing a course plan based on the provided topic, timeline, difficulty, and custom instructions.",
            "parameters": course_plan_schema
            }
        }
    ]
use_google = False

def generate_course_plan(topic, timeline, difficulty, custom_instructions):
    system_prompt = f"""
    You are a course assistant that helps students to create a course plan based on their topic, timeline and difficulty.
    Output a JSON object representing the course plan with the provided schema. 

    Topic: {topic}
    Timeline: {timeline}
    Difficulty: {difficulty}
    Custom Instructions: {custom_instructions}
    """
    if use_google:
        endpoint = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
        model = "gemini-2.0-flash"
        api_key = os.environ['API_KEY']
    else:
        
        endpoint = 'http://Bedroc-Proxy-xVtSm3tV6xYe-1727257641.us-east-1.elb.amazonaws.com/api/v1/chat/completions'
        api_key = os.environ['BEDROCK_API_KEY']
        model = 'us.anthropic.claude-3-5-haiku-20241022-v1:0'
        
    output = call_model(system_prompt, endpoint, api_key, model, tools = tools) # Pass tools to the model call
    if output is not None and 'tool_calls' in output and output['tool_calls'] is not None:        
        for tool_call in output['tool_calls']:
            return tool_call['function']['arguments']
    else:
        print(f"Error: LLM did not return a valid tool call. Output: {output}")
        return None
