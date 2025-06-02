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

    # Attempt to get user_id from Authorization header (API Gateway direct call)
    auth_header = event.get('headers', {}).get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        try:
            token = auth_header.split(' ')[1]
            payload_b64 = token.split('.')[1]
            payload_b64 += '=' * (-len(payload_b64) % 4)
            decoded_payload = base64.b64decode(payload_b64).decode('utf-8')
            payload_json = json.loads(decoded_payload)
            user_id = payload_json.get('sub')
        except Exception as e:
            print(f"Error decoding token or extracting sub: {str(e)}")
            return {
                'statusCode': 401,
                'body': json.dumps({'error': f'Invalid token: {str(e)}'})
            }
    
    # If user_id not found in token, try to get it from queryStringParameters (Step Function call)
    # The Step Function definition passes user_id in event.queryStringParameters.user_id
    if not user_id:
        user_id = data.get('user_id') 

    # Validate that user_id was obtained
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
    # get item with key and sort key
    item = table.get_item(Key={'CourseID': course_id, 'UserID': user_id})
    course = item['Item']    
        
    if chapter_id:
        for chapter in course['chapters']:
            if chapter['id'] == chapter_id:
                course = chapter
                break
    return {
        'statusCode': 200,
        'body': json.dumps(course)
    }
