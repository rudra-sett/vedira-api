import json
import boto3
import os
import base64

def lambda_handler(event, context):
    
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
                'body': json.dumps({'error': 'Missing or malformed Authorization header'})
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
                'body': json.dumps({'error': 'User ID (sub) not found in token'})
            }
    except Exception as e:
        print(f"Error decoding token or extracting sub: {str(e)}")
        return {
            'statusCode': 401,
            'body': json.dumps({'error': f'Invalid token: {str(e)}'})
        }

    if not all([course_id, chapter_id, lesson_id]):
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing required query string parameters: course_id, chapter_id, or lesson_id'})
        }

    content_key = f'{course_id}-{chapter_id}-{lesson_id}.json'
    s3 = boto3.client('s3')

    try:
        bucket_name = os.environ.get('LESSON_BUCKET_NAME')
        if not bucket_name:
            raise ValueError("LESSON_BUCKET_NAME environment variable not set.")
        response = s3.get_object(Bucket=bucket_name, Key=content_key)
        content = response['Body'].read().decode('utf-8')
        return {
            'statusCode': 200,
            'body': content
        }
    except s3.exceptions.NoSuchKey:
        return {
            'statusCode': 404,
            'body': 'Content not found'
        }
    except Exception as e:
        print(e)
        return {
            'statusCode': 500,
            'body': 'Some other error!'
        }
