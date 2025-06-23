import json
import boto3
import os
import base64
from botocore.exceptions import ClientError # For DynamoDB specific errors

sfn_client = boto3.client('stepfunctions')
dynamodb_resource = boto3.resource('dynamodb')

def handler(event, context):
    """
    Checks the status of a Step Functions execution and/or
    chapter generation statuses from DynamoDB.
    """
    try:
        query_params = event.get('queryStringParameters', {})
        if query_params is None: # Ensure query_params is a dict
            query_params = {}

        # Parameters from event (API Gateway will pass them as strings)
        event_execution_arn = query_params.get('executionArn')
        event_course_id = query_params.get('course_id')
        # event_user_id = query_params.get('user_id') # User ID will be extracted from auth token if needed
        event_chapter_id = query_params.get('chapter_id')
        
        event_user_id = None # Initialize user_id

        # If course_id and chapter_id are provided, user_id must come from event context for DynamoDB lookup
        if event_course_id and event_chapter_id:
            try:
                event_user_id = event['requestContext']['authorizer']['claims']['sub']
                if not event_user_id:
                    print("User ID (sub) is missing from authorizer claims.")
                    return {
                        'statusCode': 401, # Unauthorized
                        'body': json.dumps({'error': 'User ID not found in request context (required when course_id and chapter_id are provided)'})
                    }
            except KeyError as e:
                print(f"Error accessing user_id from event context: {str(e)}")
                return {
                    'statusCode': 401, # Unauthorized
                    'body': json.dumps({'error': f'Could not extract user ID from request context: {str(e)} (required when course_id and chapter_id are provided)'})
                }
            except Exception as e:
                print(f"Unexpected error extracting user_id: {str(e)}")
                return {
                    'statusCode': 500, # Internal Server Error
                    'body': json.dumps({'error': f'An unexpected error occurred while processing user identity: {str(e)}'})
                }
        
        result = {}
        
        # --- Check Step Function Status (if executionArn is provided) ---
        if event_execution_arn:
            try:
                sfn_response = sfn_client.describe_execution(
                    executionArn=event_execution_arn
                )
                sfn_status = sfn_response.get('status')
                sfn_output_str = sfn_response.get('output')

                sfn_is_complete = sfn_status == 'SUCCEEDED'
                sfn_is_failed = sfn_status == 'FAILED' or sfn_status == 'TIMED_OUT' or sfn_status == 'ABORTED'

                result['step_function_details'] = {
                    'execution_arn': event_execution_arn,
                    'status': sfn_status,
                    'is_complete': sfn_is_complete,
                    'is_failed': sfn_is_failed,
                }
                if sfn_is_complete and sfn_output_str:
                    try:
                        result['step_function_details']['output'] = json.loads(sfn_output_str)
                    except json.JSONDecodeError:
                        result['step_function_details']['output'] = sfn_output_str # Keep as string if not JSON
                elif sfn_is_failed:
                    error_details = sfn_response.get('error')
                    cause_details = sfn_response.get('cause')
                    if error_details:
                        result['step_function_details']['error'] = error_details
                    if cause_details:
                        result['step_function_details']['cause'] = cause_details
            
            except sfn_client.exceptions.ExecutionDoesNotExist:
                print(f"Step Functions ExecutionDoesNotExist for ARN: {event_execution_arn}")
                result['step_function_details'] = {
                    'execution_arn': event_execution_arn,
                    'status': 'NOT_FOUND',
                    'error': 'Execution ARN not found.',
                    'is_complete': False,
                    'is_failed': True # Treat as failed for status checking purposes
                }
            except sfn_client.exceptions.InvalidArn:
                print(f"Step Functions InvalidArn: {event_execution_arn}")
                result['step_function_details'] = {
                    'execution_arn': event_execution_arn,
                    'status': 'INVALID_ARN',
                    'error': 'The provided execution ARN is invalid.',
                    'is_complete': False,
                    'is_failed': True
                }
            except Exception as sfn_e: # Catch other SFN client errors
                print(f"Error describing Step Function execution {event_execution_arn}: {sfn_e}")
                result['step_function_details'] = {
                    'execution_arn': event_execution_arn,
                    'status': 'ERROR',
                    'error': f"Could not retrieve Step Function status: {str(sfn_e)}",
                    'is_complete': False,
                    'is_failed': True
                }
        
        # --- Check Chapter Statuses from DynamoDB (if all IDs are provided) ---
        if event_course_id and event_user_id and event_chapter_id:
            course_table_name = os.environ.get('COURSE_TABLE_NAME')
            if not course_table_name:
                result['chapter_generation_status_error'] = 'Server configuration error: Course table name not set.'
            else:
                course_table = dynamodb_resource.Table(course_table_name) # type: ignore
                
                try:
                    # Use actual DynamoDB key names: CourseID, UserID
                    db_response = course_table.get_item(
                        Key={'CourseID': event_course_id, 'UserID': event_user_id}
                    )
                    item = db_response.get('Item', {})
                    
                    chapters_status_map = item.get('chapters_status', {})
                    chapter_specific_statuses = chapters_status_map.get(event_chapter_id, {})
                    
                    lessons_status = chapter_specific_statuses.get('lessons_status', 'PENDING')
                    mcqs_status = chapter_specific_statuses.get('mcqs_status', 'PENDING')
                    flashcards_status = chapter_specific_statuses.get('flashcards_status', 'PENDING')
                    last_updated = chapter_specific_statuses.get('last_updated', None)
                    
                    result['chapter_generation_status'] = {
                        'course_id': event_course_id,
                        'chapter_id': event_chapter_id,
                        'user_id': event_user_id, # Include user_id in response for clarity
                        'lessons_status': lessons_status,
                        'mcqs_status': mcqs_status,
                        'flashcards_status': flashcards_status,
                        'last_updated': last_updated
                    }
                except ClientError as db_e:
                    print(f"DynamoDB ClientError fetching chapter status: {db_e}")
                    result['chapter_generation_status'] = {
                        'error': f"DynamoDB error fetching chapter statuses: {db_e.response.get('Error', {}).get('Code', 'UnknownError')}"
                    }
                except Exception as db_e: # Catch any other unexpected errors during DB interaction
                    print(f"Unexpected error fetching from DynamoDB: {db_e}")
                    result['chapter_generation_status'] = {
                        'error': f"Could not fetch chapter statuses from DynamoDB: {str(db_e)}"
                    }
        
        # If no relevant parameters were provided or no operations could be performed
        # event_user_id is now derived from token if course_id and chapter_id are present
        if not result or (not event_execution_arn and not (event_course_id and event_chapter_id)): # user_id is implicitly handled by token extraction if this path is taken
             return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Required query string parameters missing. Provide either "executionArn" or both "course_id" and "chapter_id". User ID is derived from Authorization token.'})
            }

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': json.dumps(result)
        }

    except Exception as e:
        print(f"Error checking execution status: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': json.dumps({'error': str(e)})
        }
