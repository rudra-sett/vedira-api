import json
import boto3
import os
import base64
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*", # Add CORS headers for all responses
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
    }
    
    try:
        data = event["queryStringParameters"]
        if data is None: # If there are no query string parameters
             data = {}
    except KeyError: # If "queryStringParameters" itself is missing
        data = {}
        
    course_id = data.get('course_id')
    # user_id = data['user_id'] # User ID will be extracted from the auth token
    chapter_id = data.get('chapter_id')
    lesson_id = data.get('lesson_id')

    # Extract User ID from the Authorization header
    try:
        auth_header = event.get('headers', {}).get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Missing or malformed Authorization header'}),
                'headers': headers
            }
        
        token = auth_header.split(' ')[1]
        payload_b64 = token.split('.')[1]
        payload_b64 += '=' * (-len(payload_b64) % 4)
        decoded_payload = base64.b64decode(payload_b64).decode('utf-8')
        payload_json = json.loads(decoded_payload)
        user_id = payload_json.get('sub') # user_id is extracted, though not used in S3 key for this function

        if not user_id: # Still good to validate it was present in token
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'User ID (sub) not found in token'}),
                'headers': headers
            }
    except Exception as e:
        print(f"Error decoding token or extracting sub: {str(e)}")
        return {
            'statusCode': 401,
            'body': json.dumps({'error': f'Invalid token: {str(e)}'}),
            'headers': headers
        }

    if not all([course_id, chapter_id, lesson_id]):
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing required query string parameters: course_id, chapter_id, or lesson_id'}),
            'headers': headers
        }

    content_key = f'{course_id}-{chapter_id}-{lesson_id}.json'
    s3 = boto3.client('s3')
    
    bucket_name = os.environ.get('LESSON_BUCKET_NAME')
    if not bucket_name:
        print("Error: LESSON_BUCKET_NAME environment variable not set.")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Server configuration error: Lesson bucket name not set.'}),
            'headers': headers
        }

    try:
        response = s3.get_object(Bucket=bucket_name, Key=content_key)
        content = response['Body'].read().decode('utf-8')
        
        return {
            'statusCode': 200,
            'body': content, 
            'headers': headers 
        }
    except s3.exceptions.NoSuchKey:
        # bucket_name is guaranteed to be set here due to the check above
        print(f"Content not found in S3: s3://{bucket_name}/{content_key}")
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Lesson content not found.'}),
            'headers': headers
        }
    except ClientError as e:
        print(f"S3 ClientError getting lesson content: {str(e)}")
        return {
            'statusCode': 500, 
            'body': json.dumps({'error': f'Failed to retrieve lesson content from S3: {str(e)}'}),
            'headers': headers
        }
    except Exception as e: # Catch any other unexpected errors during S3 interaction or content processing
        print(f"Unexpected error during S3 operation or content processing: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'An unexpected error occurred: {str(e)}'}),
            'headers': headers
        }
