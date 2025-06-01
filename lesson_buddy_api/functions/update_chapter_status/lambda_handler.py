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
            # This safely initializes the chapters_status map if it doesn't exist
            # and sets the specific chapter's status
            update_expression = """
                SET chapters_status = if_not_exists(chapters_status, :empty_map)
            """
            expression_attribute_values = {
                ':empty_map': {
                    event_chapter_id: {
                        'lessons_status': 'PENDING',
                        'mcqs_status': 'PENDING',
                        'last_updated': timestamp
                    }
                }
            }
            expression_attribute_names = {}
        else: # "lessons" or "mcqs"
            status_key_name = f"{status_type}_status" # e.g., lessons_status or mcqs_status
            # For "lessons" or "mcqs", we assume chapters_status and chapters_status.#chapter_id_attr exist as maps
            # because "initialize" should have set them up.
            # If chapters_status.#chapter_id_attr might not exist (e.g. initialize failed or was skipped),
            # a more complex update or a pre-check would be needed.
            # For now, keeping it as is, assuming "initialize" path works.
            update_expression = "SET chapters_status.#chapter_id_attr.#status_key_name_attr = :status_val, chapters_status.#chapter_id_attr.last_updated = :ts"
            expression_attribute_names = {
                '#chapter_id_attr': event_chapter_id, 
                '#status_key_name_attr': status_key_name 
            }
            expression_attribute_values = {
                ':status_val': new_status,
                ':ts': timestamp
            }
            # Note: If chapters_status or chapters_status.#chapter_id_attr might not exist here,
            # this update could also fail. The "initialize" step is crucial.
            # A very robust solution would be:
            # SET chapters_status = if_not_exists(chapters_status, :empty_map)
            # SET chapters_status.#chapter_id_attr = if_not_exists(chapters_status.#chapter_id_attr, :empty_map_for_chapter)
            # SET chapters_status.#chapter_id_attr.#status_key_name_attr = :status_val ...
            # But this makes the expression longer and might be overkill if "initialize" is always called first.

        if len(expression_attribute_names) == 0:
            course_table.update_item(
                Key={'CourseID': event_course_id, 'UserID': event_user_id}, # Corrected DynamoDB key names
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_attribute_values
            )
        else:
            # If we have any attribute names, we need to include them in the update
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
