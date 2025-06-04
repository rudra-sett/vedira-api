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

        # Extract User ID from the event context
        try:
            UserID = event['requestContext']['authorizer']['claims']['sub']
            if not UserID:
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
            print(f"Error accessing UserID from event context: {str(e)}")
            return {
                'statusCode': 401, # Unauthorized
                'body': json.dumps({'error': f'Could not extract user ID from request context: {str(e)}'}),
                'headers': headers
            }
        except Exception as e:
            # Catch any other unexpected errors during UserID extraction
            print(f"Unexpected error extracting UserID: {str(e)}")
            return {
                'statusCode': 500, # Internal Server Error
                'body': json.dumps({'error': f'An unexpected error occurred while processing user identity: {str(e)}'}),
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
