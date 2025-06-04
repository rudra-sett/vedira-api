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
                'headers': headers
            }
    except KeyError as e:
        # This handles cases where the path to 'sub' might be missing
        print(f"Error accessing user_id from event context: {str(e)}")
        return {
            'statusCode': 401, # Unauthorized
            'body': json.dumps({'error': f'Could not extract user ID from request context: {str(e)}'}),
            'headers': headers
        }
    except Exception as e:
        # Catch any other unexpected errors during user_id extraction
        print(f"Unexpected error extracting user_id: {str(e)}")
        return {
            'statusCode': 500, # Internal Server Error
            'body': json.dumps({'error': f'An unexpected error occurred while processing user identity: {str(e)}'}),
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
