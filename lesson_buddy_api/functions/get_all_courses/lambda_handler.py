import json
import boto3
import os

def lambda_handler(event, context):
    
    print(event)
    data = event["queryStringParameters"]
    UserID = data["user_id"]

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
