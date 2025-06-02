import json
import boto3
import os
import base64
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
    }

    try:
        print(event)

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
            UserID = payload_json.get('sub')

            if not UserID:
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

        table_name = os.environ.get('COURSE_TABLE_NAME')
        if not table_name:
            # This is a server configuration error, should ideally not happen if CDK sets it
            print("Error: COURSE_TABLE_NAME environment variable not set.")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Server configuration error: Course table name not set.'}),
                'headers': headers
            }

        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(table_name) # type: ignore
        
        try:
            response = table.query(
                IndexName='UserID-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('UserID').eq(UserID) # type: ignore
            )
            items = response.get('Items', [])
        except ClientError as e:
            print(f"DynamoDB ClientError querying courses: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': f'Could not retrieve courses: {str(e)}'}),
                'headers': headers
            }

        course_list = []
        for item in items:
            course_id = item.get('CourseID')
            title = item.get('title')
            description = item.get('description')
            if course_id and title is not None and description is not None: # Ensure all required fields are present
                course_list.append({
                    'CourseID': course_id,
                    'title': title,
                    'description': description
                })
            else:
                print(f"Warning: Skipping item due to missing fields: {item}")
        
        print(course_list)

        return {
            'statusCode': 200,
            'body': json.dumps(course_list),
            'headers': headers
        }

    except Exception as e:
        # Catch-all for any other unexpected errors
        print(f"Unexpected error in get_all_courses: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'An unexpected server error occurred: {str(e)}'}),
            'headers': headers
        }
