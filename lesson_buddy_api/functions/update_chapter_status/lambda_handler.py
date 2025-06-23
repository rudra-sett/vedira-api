import json
import os
import boto3
from botocore.exceptions import ClientError
import datetime
import base64
import json # Already imported but good to ensure

dynamodb_resource = boto3.resource('dynamodb') # Renamed to avoid potential naming conflicts

def lambda_handler(event, context):
    course_table_name = os.environ.get('COURSE_TABLE_NAME')
    if not course_table_name:
        print("Error: COURSE_TABLE_NAME environment variable not set.")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Server configuration error: Course table name not set.'})
        }
    course_table = dynamodb_resource.Table(course_table_name) # type: ignore

    try:
        print(f"Received event: {json.dumps(event)}")

        # Event parameters - directly from Step Function payload
        event_course_id = event.get('course_id')
        event_user_id = event.get('user_id') # User ID is passed directly by the Step Function
        event_chapter_id = event.get('chapter_id')
        status_type = event.get('status_type') # "lessons" or "mcqs"
        new_status = event.get('new_status') # "PENDING", "GENERATING", "COMPLETED", "FAILED"

        # Validate required parameters including event_user_id from the event payload
        if not all([event_course_id, event_user_id, event_chapter_id, status_type, new_status]):
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing required parameters: course_id, user_id, chapter_id, status_type, or new_status from event payload'})
            }

        if status_type not in ["lessons", "mcqs", "flashcards"]:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid status_type. Must be "lessons", "mcqs", or "flashcards".'})
            }
        
        if new_status not in ["PENDING", "GENERATING", "COMPLETED", "FAILED"]:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid new_status. Must be "PENDING", "GENERATING", "COMPLETED", or "FAILED".'})
            }

        timestamp = datetime.datetime.utcnow().isoformat()
        status_key_name = f"{status_type}_status" # e.g., lessons_status or mcqs_status

        update_expression = "SET chapters_status.#chapter_id_attr.#status_key_name_attr = :status_val, chapters_status.#chapter_id_attr.last_updated = :ts"
        
        expression_attribute_names = {
            '#chapter_id_attr': event_chapter_id, 
            '#status_key_name_attr': status_key_name 
        }
        
        expression_attribute_values = {
            ':status_val': new_status,
            ':ts': timestamp
        }

        course_table.update_item(
            Key={'CourseID': event_course_id, 'UserID': event_user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ConditionExpression="attribute_exists(CourseID) AND attribute_exists(UserID)" # Ensure the item exists
        )

        return {
            'statusCode': 200,
            'body': json.dumps({'message': f'Successfully updated {status_type} status for chapter {event_chapter_id} to {new_status}.'})
        }
    
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            print(f"ConditionalCheckFailedException: Item with CourseID {event_course_id} and UserID {event_user_id} not found or condition failed.")
            return {
                'statusCode': 404,
                'body': json.dumps({'error': f'Course with ID {event_course_id} for user {event_user_id} not found.'})
            }
        else:
            print(f"DynamoDB ClientError: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': f'DynamoDB error: {str(e)}'})
            }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'An unexpected error occurred: {str(e)}'})
        }
