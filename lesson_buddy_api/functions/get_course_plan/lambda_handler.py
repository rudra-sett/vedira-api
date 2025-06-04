import json
import boto3
import os
import base64

def lambda_handler(event, context):
    print(event)
    
    try:
        data = event["queryStringParameters"]
        if data is None: # If there are no query string parameters
             data = {} 
    except KeyError: # If "queryStringParameters" itself is missing
        data = {}

    course_id = data.get('course_id') # Use .get() for safety
    chapter_id = data.get('chapter_id', None)
    user_id = None

    # Attempt to get user_id from event context (API Gateway with Lambda Authorizer)
    try:
        user_id = event['requestContext']['authorizer']['claims']['sub']
        if not user_id:
            # This might happen if 'sub' is empty, though unlikely with a proper authorizer
            print("User ID (sub) is present but empty in authorizer claims.")
            # We will fall through to the next method of getting user_id
    except KeyError:
        # 'requestContext' or 'authorizer' or 'claims' or 'sub' might be missing
        # This is expected if the call is not from API Gateway with this authorizer (e.g., Step Function)
        print("User ID not found in event.requestContext.authorizer.claims.sub. Trying queryStringParameters.")
    except Exception as e:
        # Catch any other unexpected errors during user_id extraction from context
        print(f"Unexpected error extracting user_id from event context: {str(e)}")
        # Fall through to try queryStringParameters, but log the error.

    # If user_id not found in event context (e.g. Step Function call),
    # try to get it from queryStringParameters.
    if not user_id:
        user_id = data.get('user_id')
        if user_id:
            print("User ID obtained from queryStringParameters.")
        else:
            print("User ID also not found in queryStringParameters.")

    # Validate that user_id was obtained by either method
    if not user_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'User ID could not be determined from token or event payload.'})
        }

    if not course_id: # course_id is still expected from query params (or direct event payload for SFN)
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing required parameter: course_id'})
        }

    # pull from dynamo
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('COURSE_TABLE_NAME')
    if not table_name:
        raise ValueError("COURSE_TABLE_NAME environment variable not set.")
    table = dynamodb.Table(table_name)
    
    try:
        item_response = table.get_item(Key={'CourseID': course_id, 'UserID': user_id})
    except Exception as e: # Consider more specific boto3 client errors
        print(f"Error getting item from DynamoDB: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Could not retrieve course data: {str(e)}'})
        }

    if 'Item' not in item_response:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': f'Course with ID {course_id} not found for user.'})
        }
    
    course_data = item_response['Item']
        
    if chapter_id:
        found_chapter = None
        if 'chapters' in course_data and isinstance(course_data['chapters'], list):
            for chapter in course_data['chapters']:
                if isinstance(chapter, dict) and chapter.get('id') == chapter_id:
                    found_chapter = chapter
                    break
        
        if found_chapter:
            return {
                'statusCode': 200,
                'body': json.dumps(found_chapter)
            }
        else:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': f'Chapter with ID {chapter_id} not found in course {course_id}.'})
            }
    else: # No chapter_id requested, return the whole course
        return {
            'statusCode': 200,
            'body': json.dumps(course_data)
        }
