import json
import boto3
import os
import base64

def lambda_handler(event, context):
    
    print(event)
    # data = event["queryStringParameters"] # UserID will be extracted from auth token
    # UserID = data["user_id"]

    # Extract User ID from the Authorization header
    try:
        auth_header = event.get('headers', {}).get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Missing or malformed Authorization header'})
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
                'body': json.dumps({'error': 'User ID (sub) not found in token'})
            }
    except Exception as e:
        print(f"Error decoding token or extracting sub: {str(e)}")
        return {
            'statusCode': 401,
            'body': json.dumps({'error': f'Invalid token: {str(e)}'})
        }

    # get all items from LB-CourseTable based on UserID, using UserID-index index

    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('COURSE_TABLE_NAME')
    if not table_name:
        raise ValueError("COURSE_TABLE_NAME environment variable not set.")
    table = dynamodb.Table(table_name) # type: ignore
    items = table.query(
        IndexName='UserID-index',
        KeyConditionExpression=boto3.dynamodb.conditions.Key('UserID').eq(UserID) # type: ignore
        )['Items']

    course_list = []
    for item in items:
        course_list.append({'CourseID' : item['CourseID'],
        'title' : item['title'],
        'description' : item['description']})
    
    print(course_list)

    return {
        'statusCode': 200,
        'body': json.dumps(course_list)
    }
