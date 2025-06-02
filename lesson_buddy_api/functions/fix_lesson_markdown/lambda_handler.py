import json
from urllib import request, parse, error as urllib_error
import boto3
import time
import os

# --- Copied from generate_lesson_content/lambda_handler.py ---
def get_api_info(model):
    if model == 'gemini-2.5-flash':
        url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
        api_key = os.environ['API_KEY']
        return url, api_key, 'gemini-2.5-flash-preview-05-20'
    if model == 'gemini-2.5-pro':
        url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
        api_key = os.environ['API_KEY']
        return url, api_key, 'gemini-2.5-pro-preview-05-06'
    if model == 'claude-4-sonnet':
        url = 'http://Bedroc-Proxy-xVtSm3tV6xYe-1727257641.us-east-1.elb.amazonaws.com/api/v1/chat/completions'
        api_key = os.environ['BEDROCK_API_KEY']
        return url, api_key, 'us.anthropic.claude-sonnet-4-20250514-v1:0'
    if model == 'claude-3.7-sonnet':
        url = 'http://Bedroc-Proxy-xVtSm3tV6xYe-1727257641.us-east-1.elb.amazonaws.com/api/v1/chat/completions'
        api_key = os.environ['BEDROCK_API_KEY']
        return url, api_key, 'us.anthropic.claude-3-7-sonnet-20250219-v1:0'
    if model == 'claude-3.5-haiku':
        url = 'http://Bedroc-Proxy-xVtSm3tV6xYe-1727257641.us-east-1.elb.amazonaws.com/api/v1/chat/completions'
        api_key = os.environ['BEDROCK_API_KEY']
        return url, api_key, 'us.anthropic.claude-3-5-haiku-20241022-v1:0'
    if model == 'gemini-2.0-flash':
        url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
        api_key = os.environ['API_KEY']
        return url, api_key, 'gemini-2.0-flash-001'
    if model == 'gemini-2.0-flash-lite':
        url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
        api_key = os.environ['API_KEY']
        return url, api_key, 'gemini-2.0-flash-lite-001'
    raise ValueError(f"Unsupported model: {model}")

def call_model(system_prompt, prompt, messages=None, output_format=None, tools=None, model='gemini-2.5-flash'):
    url, api_key, model_name = get_api_info(model) # Renamed 'model' from get_api_info to 'model_name'

    data = {
        "model": model_name, # Use model_name here
        "messages": [],
        "max_tokens": 8192
    }

    data['messages'].append({"role": "system", "content": system_prompt})

    if messages is not None:
        data['messages'].extend(messages)
    
    data['messages'].append({"role": "user", "content": prompt})
    
    if output_format:
        data['response_format'] = {
            "type": "json_schema",
            "json_schema": {
                "name": "output",
                "schema": output_format  
            }
        }

    if tools:
        data['tools'] = tools

    data_bytes = json.dumps(data).encode('utf-8')
    
    max_retries = 5
    base_delay = 1
    max_delay = 10
    
    for attempt in range(max_retries + 1):
        req = request.Request(url, data=data_bytes)
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {api_key}')
        
        try:
            with request.urlopen(req) as resp:
                if resp.status == 200:
                    content = resp.read()
                    output = json.loads(content)
                    # print(output) # Consider removing or conditionalizing print for production
                    return output['choices'][0]['message']
                else:
                    # Log more details for HTTP errors
                    error_content = resp.read().decode('utf-8') if resp.length > 0 else "No content" # type: ignore
                    print(f"HTTP Error: {resp.status} - {resp.reason}. Response: {error_content}")
                    raise urllib_error.HTTPError(url, resp.status, resp.reason, resp.headers, resp.fp) # type: ignore
                    
        except Exception as e:
            if attempt == max_retries:
                print(f"Error: Final attempt failed after {max_retries} retries: {e}")
                return None
            
            is_http_error = isinstance(e, urllib_error.HTTPError)
            is_url_error = isinstance(e, urllib_error.URLError)
                
            if (is_http_error and e.code == 503) or is_url_error:
                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = delay * 0.1 * (0.5 - (0.5 * attempt / max_retries))
                sleep_time = delay + jitter
                
                print(f"Attempt {attempt + 1} failed. Retrying in {sleep_time:.2f} seconds... Error: {e}")
                time.sleep(sleep_time)
            else:
                print(f"Non-retryable error: {e}")
                return None
    return None # Should be unreachable if loop completes, but as a fallback

# --- End of copied functions ---

def _fix_markdown_for_all_sections(lesson_dict):
    """
    Iterates through a dictionary of lesson content and uses an LLM to fix markdown.
    """
    if not isinstance(lesson_dict, dict):
        print(f"Error: Expected a dictionary for lesson_dict, got {type(lesson_dict)}. Returning as is.")
        return lesson_dict

    fixed_lesson_dict = {}
    system_prompt = """You are a markdown expert. The following text is a part of an educational lesson. 
Please review the provided text and correct any markdown formatting issues. 
Ensure that headings (e.g., #, ##), lists (e.g., *, -, 1.), bold/italic text (e.g., **, *, __, _), 
code blocks (e.g., ``` ```), inline code (e.g., ` `), blockquotes (e.g., >), and links (e.g., [text](url)) 
are correctly formatted according to standard markdown syntax.
Return only the corrected markdown text, without any additional explanations or commentary.
If the markdown is already correct, return the original text.
If the provided text appears to be a section of a larger document and does not begin with a markdown header (e.g., #, ##, ###), please add an appropriate H2 header (e.g., "## Section Title") at the beginning of the text. Infer a suitable title from the content if one is not obvious. Make sure not to include the section number in the header. If there is an H1 header, please replace it with an H2 header.
Finally, if any content appears incomplete, please ensure it is complete and coherent, as if it were a standalone section of a lesson. Only add what is necessary to make it complete, without altering the original meaning or intent of the content.
"""
    for section_id, section_content in lesson_dict.items():
        if not isinstance(section_content, str) or not section_content.strip():
            print(f"Skipping markdown fixing for section {section_id} due to empty or non-string content.")
            fixed_lesson_dict[section_id] = section_content
            continue

        print(f"Attempting to fix markdown for section: {section_id}")
        try:
            # Using a potentially faster/cheaper model for markdown fixing
            model_output = call_model(system_prompt, section_content, model='gemini-2.5-flash') 
            if model_output and 'content' in model_output:
                content_to_fix = model_output['content']
                corrected_content = "" # Initialize

                # Pattern 1: ```markdown\n{content}\n```
                if content_to_fix.startswith("```markdown\n") and content_to_fix.endswith("\n```"):
                    corrected_content = content_to_fix[len("```markdown\n"):-len("\n```")]
                # Pattern 2: ```\n{content}\n``` (handles cases where LLM adds newlines inside the backticks)
                elif content_to_fix.startswith("```\n") and content_to_fix.endswith("\n```"):
                    corrected_content = content_to_fix[len("```\n"):-len("\n```")]
                # Pattern 3: ```{content}``` (no newlines immediately after/before backticks, content might be multi-line)
                elif content_to_fix.startswith("```") and content_to_fix.endswith("```"):
                    corrected_content = content_to_fix[3:-3]
                # Pattern 4: `{content}` (single backticks)
                elif content_to_fix.startswith("`") and content_to_fix.endswith("`"):
                    corrected_content = content_to_fix[1:-1]
                else:
                    corrected_content = content_to_fix # No stripping needed
                
                # Final strip for any leading/trailing whitespace that might remain or be part of the content itself.
                fixed_lesson_dict[section_id] = corrected_content.strip()
                print(f"Markdown fixed for section: {section_id}")
            else:
                print(f"Error: call_model did not return expected output for markdown fixing of section {section_id}. Using original content.")
                fixed_lesson_dict[section_id] = section_content
        except Exception as e:
            print(f"Exception during markdown fixing for section {section_id}: {e}. Using original content.")
            fixed_lesson_dict[section_id] = section_content
            
    return fixed_lesson_dict

def lambda_handler(event, context):
    print("Fix Lesson Markdown Lambda invoked with event:", json.dumps(event))

    # The event is expected to be the output of the generate_lesson_content Lambda
    # which should include: chapter_id, lesson_id, lesson_content, course_id
    
    lesson_content_raw = event.get('lesson_content')
    chapter_id = event.get('chapter_id')
    lesson_id = event.get('lesson_id')
    course_id = event.get('course_id')

    if not all([lesson_content_raw, chapter_id, lesson_id, course_id]):
        missing_keys = [k for k, v in {'lesson_content': lesson_content_raw, 'chapter_id': chapter_id, 'lesson_id': lesson_id, 'course_id': course_id}.items() if not v]
        error_msg = f"Missing required keys in input event: {', '.join(missing_keys)}"
        print(error_msg)
        raise ValueError(error_msg)

    # Ensure lesson_content_raw is a dictionary
    if not isinstance(lesson_content_raw, dict):
        error_msg = f"Expected 'lesson_content' to be a dictionary, but got {type(lesson_content_raw)}"
        print(error_msg)
        # Attempt to parse if it's a stringified JSON, otherwise raise error
        if isinstance(lesson_content_raw, str):
            try:
                lesson_content_raw = json.loads(lesson_content_raw)
                if not isinstance(lesson_content_raw, dict): # Re-check after parsing
                    raise ValueError(f"Parsed 'lesson_content' is not a dictionary, but {type(lesson_content_raw)}")
            except json.JSONDecodeError:
                raise ValueError(f"Could not parse 'lesson_content' string as JSON: {lesson_content_raw}")
        else:
            raise ValueError(error_msg) # Raise if not dict and not string

    print(f"Processing lesson: CourseID={course_id}, ChapterID={chapter_id}, LessonID={lesson_id}")

    fixed_lesson_content = _fix_markdown_for_all_sections(lesson_content_raw)

    # Save the fixed lesson content to S3
    s3 = boto3.client('s3')
    bucket_name = os.environ.get('LESSON_BUCKET_NAME')
    if not bucket_name:
        error_msg = "LESSON_BUCKET_NAME environment variable not set."
        print(error_msg)
        raise ValueError(error_msg)
    
    s3_key = f"{course_id}-{chapter_id}-{lesson_id}.json"
    try:
        s3.put_object(Bucket=bucket_name, Key=s3_key, Body=json.dumps(fixed_lesson_content))
        print(f"Successfully saved fixed lesson content to S3: s3://{bucket_name}/{s3_key}")
    except Exception as e:
        print(f"Error saving fixed lesson content to S3 (s3://{bucket_name}/{s3_key}): {e}")
        raise # Re-raise the exception to indicate failure

    # Return the necessary IDs and the fixed content for the next step (e.g., mark_lesson_generated)
    # The structure should match what mark_lesson_generated expects or what the Step Function needs to pass.
    # Based on the original Step Function, mark_lesson_generated expects 'updated_lessons' and 'course_plan'.
    # We need to ensure the output of this Lambda aligns with the input of the next.
    # For now, returning the key identifiers and the fixed content.
    # The Step Function definition will need to map this output correctly.
    
    s3_url = f"s3://{bucket_name}/{s3_key}"
    
    return {
        "chapter_id": chapter_id,
        "lesson_id": lesson_id,
        "course_id": course_id,         
        "lesson_s3_url": s3_url # Return S3 URL instead of content
    }
