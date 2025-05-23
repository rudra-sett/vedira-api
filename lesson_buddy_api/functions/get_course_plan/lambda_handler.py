import json
import boto3
import os

def lambda_handler(event, context):
    print(event)
    data = event["queryStringParameters"]
    # data = json.loads(data)
    course_id = data['course_id']
    user_id = data['user_id']
    chapter_id = data.get('chapter_id', None)

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
