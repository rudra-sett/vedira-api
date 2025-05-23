import json
import boto3
from urllib import request, parse
import base64
import uuid
import os

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
        user_id = data.get('user_id', None)

        course_plan = json.loads(generate_course_plan(topic, timeline, difficulty, custom_instructions)) # type: ignore
        course_plan['CourseID'] = str(uuid.uuid4())
        course_plan['UserID'] = user_id

        print(course_plan)

        # set completed, generated to false for every lesson
        for chapter in course_plan['chapters']:
            for lesson in chapter['lessons']:
                lesson['completed'] = False
                lesson['generated'] = False
        
        # save to dynamodb
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('COURSE_TABLE_NAME')
        if not table_name:
            raise ValueError("COURSE_TABLE_NAME environment variable not set.")
        table = dynamodb.Table(table_name) # type: ignore
        table.put_item(Item=course_plan)
        print('Saved to DynamoDB')

        return {
            'statusCode': 200,
            'body': json.dumps(course_plan)
        }
    except Exception as e:
        print(e)        
        return {
            'statusCode': 200,
            'body': call_model(f'Please output a debug message based on this error: {e}')
        }


url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
api_key = os.environ.get('API_KEY', '')
headers = {'Content-Type': 'application/json', 'Authorization' : f'Bearer {api_key}'}

def call_model(prompt,output_format = None):
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
            content = resp.read()
            print(content.decode('utf-8'))
            output = json.loads(content)
            print(output)
            return output['choices'][0]['message']['content']
    except Exception as e:
        print(f"Error: {e}")
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
