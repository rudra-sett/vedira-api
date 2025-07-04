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

# Create AWS clients
bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
s3_client = boto3.client("s3")
sfn_client = boto3.client("stepfunctions") # Initialize Step Functions client

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

        # Construct the S3 URL in s3://bucket/key format
        image_url = f"s3://{bucket_name}/{s3_key}"
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
        document_content = data.get('document_content', None) # New: Base64 encoded document content
        document_type = data.get('document_type', None)       # New: MIME type of the document (e.g., 'image/png', 'application/pdf')

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
            llm_future = executor.submit(generate_course_plan, topic, timeline, difficulty, custom_instructions, document_content, document_type)
            image_future = executor.submit(generate_course_image, topic, course_id)

            try:
                course_plan = llm_future.result() # Wait for LLM result
                if course_plan is None: # call_model now returns None on error
                    raise ValueError("Failed to generate course plan from LLM: Received no content.")                
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
                    'flashcards_status': 'PENDING',
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

        # Trigger the Step Function for course content generation
        step_function_arn = os.environ.get('STEP_FUNCTION_ARN')
        if step_function_arn:
            try:
                # For each chapter, start a Step Function execution
                for chapter in course_plan['chapters']:
                    chapter_id = chapter.get('id')
                    if chapter_id:
                        sfn_input = {
                            "course_id": course_id,
                            "user_id": user_id,
                            "chapter_id": chapter_id
                        }
                        sfn_client.start_execution(
                            stateMachineArn=step_function_arn,
                            input=json.dumps(sfn_input)
                        )
                        print(f"Started Step Function for chapter {chapter_id} of course {course_id}")
                        # we only want to do it for the first chapter
                        break
            except ClientError as e:
                print(f"Error starting Step Function execution: {str(e)}")
                # Do not return error, as course plan is already saved. Log and continue.
            except Exception as e:
                print(f"Unexpected error triggering Step Function: {str(e)}")
                # Do not return error, as course plan is already saved. Log and continue.
        else:
            print("Warning: STEP_FUNCTION_ARN environment variable not set. Step Function not triggered.")

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
            "description": "Output a JSON object representing a course plan based on the provided topic, timeline, difficulty, custom instructions, and optionally, document content.",
            "parameters": course_plan_schema
            }
        }
    ]
use_google = False

def generate_course_plan(topic, timeline, difficulty, custom_instructions, document_content, document_type):
    system_prompt = f"""
    You are a course assistant that helps students to create a course plan based on their topic, timeline and difficulty.
    Output a JSON object representing the course plan with the provided schema. 

    Topic: {topic}
    Timeline: {timeline}
    Difficulty: {difficulty}
    Custom Instructions: {custom_instructions}
    """    
        
    # output = call_model(system_prompt, endpoint, api_key, model, tools = tools) # Pass tools to the model call
    if document_content:
        try:
            decoded_document = base64.b64decode(document_content)
        except Exception as e:
            print("Failed to decode base64 string: %s", e)
            # Handle the error appropriately, maybe raise a ValueError
            raise ValueError("Invalid base64 string provided.") from e

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "text": system_prompt
                    },
                    {
                        "document": {
                            "name": "input_document",
                            "format": document_type,
                            "source": {
                                "bytes": decoded_document
                            }
                    }
                    }
                ]
            }]
    else:
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "text": system_prompt
                    }
                ]
            }]
        

    tool_config = {
    "tools": [
        {
            "toolSpec": {
                "name": "top_song",
                "description": "Get the most popular song played on a radio station.",
                "inputSchema": {
                    "json": course_plan_schema
                }
            }
        }
    ]
}
    
    response = bedrock_client.converse(
        modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",
        messages=messages,
        toolConfig=tool_config,
        inferenceConfig={
            "maxTokens": 8192,
            "temperature": 0.5,
            # "topP": 0.5
        }
    )
    output = response['output']['message']['content']

    print(output)
    
    for block in output:
        if 'toolUse' in block:
            tool_call = block['toolUse']['input']
            return tool_call

    print(f"Error: LLM did not return a valid tool call. Output: {output}")
    return None
