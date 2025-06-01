import json
import os
import boto3
import datetime

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

        # Event parameters (typically lowercase with underscores from API Gateway JSON body)
        event_course_id = event.get('course_id')
        event_user_id = event.get('user_id') 
        event_chapter_id = event.get('chapter_id')
        status_type = event.get('status_type') # "lessons", "mcqs", or "initialize"
        new_status = event.get('new_status') # "PENDING", "GENERATING", "COMPLETED", "FAILED"

        if not all([event_course_id, event_user_id, event_chapter_id, status_type]):
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing required parameters: course_id, user_id, chapter_id, or status_type'})
            }

        if status_type not in ["lessons", "mcqs", "initialize"]:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid status_type. Must be "lessons", "mcqs", or "initialize".'})
            }

        if status_type != "initialize" and not new_status:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'new_status is required when status_type is "lessons" or "mcqs".'})
            }
        
        if status_type != "initialize" and new_status not in ["PENDING", "GENERATING", "COMPLETED", "FAILED"]:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid new_status. Must be "PENDING", "GENERATING", "COMPLETED", or "FAILED".'})
            }

        timestamp = datetime.datetime.utcnow().isoformat()

        if status_type == "initialize":
            update_expression = "SET chapters_status.#chapter_id_attr = :init_status_map" # Use placeholder for chapter_id in expression
            expression_attribute_names = {
                '#chapter_id_attr': event_chapter_id # Map placeholder to actual chapter_id variable
            }
            expression_attribute_values = {
                ':init_status_map': {
                    'lessons_status': 'GENERATING',
                    'mcqs_status': 'PENDING',
                    'last_updated': timestamp
                }
            }
        else: # "lessons" or "mcqs"
            status_key_name = f"{status_type}_status" # e.g., lessons_status or mcqs_status
            # Use placeholders for chapter_id and the status key name in the expression
            update_expression = "SET chapters_status.#chapter_id_attr.#status_key_name_attr = :status_val, chapters_status.#chapter_id_attr.last_updated = :ts"
            expression_attribute_names = {
                '#chapter_id_attr': event_chapter_id, # Map placeholder to actual chapter_id variable
                '#status_key_name_attr': status_key_name # Map placeholder to actual status key name
            }
            expression_attribute_values = {
                ':status_val': new_status,
                ':ts': timestamp
            }
            # Ensure the chapter map exists, or create it
            # This part is a bit tricky with UpdateItem if chapters_status itself might not exist.
            # A safer approach for ensuring the path is to initialize chapters_status if it's null.
            # However, for simplicity here, we assume chapters_status map exists or UpdateItem creates it.
            # For a more robust solution, one might do a GetItem then PutItem, or use a conditional update.
            # A common pattern is to initialize the top-level map if it's not present.
            # For this specific update, we are setting a nested field.
            # If chapters_status.event_chapter_id does not exist, this SET operation will create it.

        course_table.update_item(
            Key={'CourseID': event_course_id, 'UserID': event_user_id}, # Corrected DynamoDB key names
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )

        return {
            'statusCode': 200,
            'body': json.dumps({'message': f'Successfully updated {status_type} status for chapter {event_chapter_id} to {new_status if new_status else "initialized"}.'})
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
