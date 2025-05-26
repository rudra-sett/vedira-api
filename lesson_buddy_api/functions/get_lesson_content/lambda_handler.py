import json
import boto3
import os

def lambda_handler(event, context):
    
    data = event["queryStringParameters"]    
    course_id = data['course_id']
    user_id = data['user_id']
    chapter_id = data.get('chapter_id')
    lesson_id = data.get('lesson_id')

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
