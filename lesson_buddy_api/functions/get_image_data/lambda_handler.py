import json
import boto3
import os
from urllib.parse import urlparse
import base64

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    try:
        print(f"Received event: {json.dumps(event)}")

        # Extract S3 URL from query string parameters for GET request
        s3_url = None
        if 'queryStringParameters' in event and event['queryStringParameters']:
            s3_url = event['queryStringParameters'].get('s3Url')

        if not s3_url:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing s3_url in query parameters'}),
                'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
            }

        # Parse the S3 URL to get bucket name and key
        parsed_url = urlparse(s3_url)
        
        bucket_name = None
        s3_key = None

        # Handle s3://bucket/key format
        if parsed_url.scheme == 's3':
            bucket_name = parsed_url.netloc
            s3_key = parsed_url.path.lstrip('/')
        # For virtual hosted style: bucket.s3.amazonaws.com/key
        elif parsed_url.netloc.endswith('.s3.amazonaws.com'):
            bucket_name = parsed_url.netloc.split('.')[0]
            s3_key = parsed_url.path.lstrip('/')
        # For path style: s3.amazonaws.com/bucket/key
        elif parsed_url.netloc == 's3.amazonaws.com':
            path_parts = parsed_url.path.lstrip('/').split('/', 1)
            if len(path_parts) > 0:
                bucket_name = path_parts[0]
            if len(path_parts) > 1:
                s3_key = path_parts[1]
        else:
            # Handle other potential S3 URL formats or return error
            print(f"Unsupported S3 URL format: {s3_url}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Unsupported S3 URL format'}),
                'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
            }

        if not bucket_name or not s3_key:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Could not extract bucket or key from S3 URL'}),
                'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
            }

        print(f"Attempting to retrieve object from bucket: {bucket_name}, key: {s3_key}")

        try:
            print(s3_key)
            # Get the object from S3
            response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
            image_data = response['Body'].read()
            content_type = response.get('ContentType', 'application/octet-stream')            

            # Return the image data directly as a binary response
            return {
            'headers': { "Content-Type": content_type },
            'statusCode': 200,
            'body': base64.b64encode(image_data).decode('utf-8'),
            'isBase64Encoded': True
        }

        except s3_client.exceptions.NoSuchKey:
            print(f"Error: Object not found at s3://{bucket_name}/{s3_key}")
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Image not found'}),
                'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
            }
        except s3_client.exceptions.ClientError as e:
            print(f"S3 Client Error: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': f'Failed to retrieve image from S3: {str(e)}'}),
                'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
            }
    except Exception as e:
        print(f"Unexpected error in get_image_data lambda: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'An unexpected server error occurred: {str(e)}'}),
            'headers': {'Content-Type': 'application/json', "Access-Control-Allow-Origin": "*"}
        }
