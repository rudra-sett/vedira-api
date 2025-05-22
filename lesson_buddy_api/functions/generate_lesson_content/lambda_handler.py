import json
from  urllib import request, parse
import boto3
import time
import os

def lambda_handler(event, context):
    # try:
    print(event)
    
    data = event['body']
    course_plan = data['course_plan']
    chapter_id = data['chapter_id']
    lesson_id = data['lesson_id']

    lesson_data = {}
    chapter_info = {}

    for c, chapter in enumerate(course_plan["chapters"]):
        if chapter['id'] == chapter_id:      
            chapter_info['title'] = chapter['title']
            chapter_info['description'] = chapter['description']
            for l, lesson in enumerate(chapter['lessons']):
                if lesson['id'] == lesson_id:
                    lesson_data = lesson
                    course_plan['chapters'][c]['lessons'][l]['generated'] = True                    
    
    lesson_content = main_agent(course_plan, lesson_data, chapter_info)

    final_lesson = "\n".join(lesson_content.values())

    # save to s3
    s3 = boto3.client('s3')
    s3.put_object(Bucket='lb-lesson-bucket', Key=f'{course_plan['CourseID']}-{chapter_id}-{lesson_id}.md', Body=final_lesson)
    
    return {        
        "chapter_id" : chapter_id,
        "lesson_id" : lesson_id                
    }


def get_api_info(provider):
    if provider == 'google':
        url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
        api_key = os.environ['API_KEY']
        return url, api_key, 'gemini-2.5-flash-preview-04-17'
    if provider == 'deepseek':
        url = 'https://api.deepseek.com/chat/completions'
        api_key = ''        
        return url, api_key,'deepseek-chat'
    if provider == 'openai':
        url = 'https://api.openai.com/v1/responses'
        api_key = ''        
        return url, api_key, 'gpt-4.1-mini-2025-04-14'

def call_model(system_prompt, prompt, messages=None, output_format=None, tools=None, provider='google'):

    url, api_key, model = get_api_info(provider)

    data = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}],
        "max_tokens": 8192
    }

    if messages:
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
    
    # Retry configuration
    max_retries = 5  # Maximum number of retries
    base_delay = 1  # Initial delay in seconds
    max_delay = 10  # Maximum delay in seconds
    
    for attempt in range(max_retries + 1):  # +1 to include the initial attempt
        req = request.Request(url, data=data_bytes)
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {api_key}')
        
        try:
            with request.urlopen(req) as resp:
                if resp.status == 200:
                    content = resp.read()
                    output = json.loads(content)
                    print(output)
                    return output['choices'][0]['message']
                else:
                    raise Exception(f"HTTP Error: {resp.status} - {resp.reason}")
                    
        except Exception as e:
            if attempt == max_retries:  # Last attempt failed
                print(f"Error: Final attempt failed after {max_retries} retries: {e}")
                return None
                
            # Check if it's a 503 error or other retryable error
            if hasattr(e, 'code') and e.code == 503 or isinstance(e, (request.HTTPError, request.URLError)):
                # Calculate delay with exponential backoff and jitter
                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = delay * 0.1 * (0.5 - (0.5 * attempt / max_retries))  # Add some jitter
                sleep_time = delay + jitter
                
                print(f"Attempt {attempt + 1} failed. Retrying in {sleep_time:.2f} seconds... Error: {e}")
                time.sleep(sleep_time)
            else:
                # Non-retryable error
                print(f"Error: {e}")
                return None

lesson_chunks = {}
generation_counts = {}

def main_agent(course_plan, lesson_data, chapter_info):
    global lesson_chunks
    global generation_counts
    # main agentic loop
    # it is instructed to create a list of requirements of the topic
    # then ask the sub-agent to generate the lesson content
    # it will also ask for a sub-agent to assess the lesson content
    # if the assessor approves the content, the main agent will add it to the course plan
    # if the assessor rejects the content, the main agent will ask the sub-agent to generate a new lesson content
    # the main agent will repeat this process until the course plan is complete
    # the main agent will return the course plan    


    system_prompt = f'''
    You are a world-class teacher who is responsible for creating a lesson for a student.
    You will be given a course plan, and a specific lesson topic.
    You will first create a list of requirements of the topic, which may include things like example problems or equations/formulas. 
    Some subjects may call for historical background, for example. In general, please encourage long-form content as much as possible.
    Emphasize this to both the lesson generator and assessor.

    Make sure to tell the assessor to be relatively critical, watching out for content length (longer is preferred, to align with a textbook or blog format).
    We don't want excessively concise/bulleted outputs.

    You have 2 tools:
    1. An agent to generate lesson content (another LLM will generate this content for you)
    2. An agent to assess the lesson content (another LLM will assess the lesson and tell you if it is good)

    Your responsibility will be to instruct these agents to the best of your ability. You can provide them system prompts
    to guide them on how to perform their respective roles. You do not have the ability to directly edit the lesson content. Only the lesson
    generator can edit it and only the assesor can view it. Your only task is to coordinate their roles together. Note that the assessor does not have access to previous feedback, nor can it edit the lesson. ONLY the content generator can modify the lesson content.

    Essentially, this is your full procedure:

    1. Determine the requirements of the lesson topic in context of the full course. Structure this as a set of "chunks" that represent individual parts of the lesson.
    2. Based on those requirements, use the generate_lesson_content tool to generate each portion of the lesson.
    3. Request an assessment from the assessor agent by prompting it to assess the lesson based on your requirements.
    4. The assessor will give you an evaluation. 
    5. If the assessor believes the lesson chunk does not meet your requirements, ask the content generator to re-create the lesson chunk based on feedback from the assessor.
    6. Repeat this until you have a full, COMPLETE lesson (not just one chunk) approved by the assessor. PLEASE avoid generating and re-assessing content repeatedly. You shouldn't stay on the same chunk for more than 3-4 iterations.

    The course the lesson is a part of is called {course_plan['title']}. The description of the course is {course_plan['description']}.
    The chapter the lesson is a part of is called {chapter_info['title']}, which is described as "{chapter_info['description']}."
    
    Here is the information on the lesson you are creating and curating content for: {lesson_data}. Ensure all aspects of the lesson are addressed.    
    The current lesson chunks, if any, are: 
    {"\n".join(lesson_chunks.keys())}
    Only complete the lesson generation after ALL aspects and portions of the lesson are completed.

    This is the number of times each lesson chunk has been re-written. Please do not exceed 3 re-writes.

    {json.dumps(generation_counts)}

    '''

    tools = [
        {
            "type": "function",
            "function": {
            "name": "generate_lesson_content",
            "description": "Requests another LLM to generate lesson content as per your instructions.",
            "parameters": {
                "type": "object",
                "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The instructions to provide the LLM to generate lesson content.",
                },
                "lesson_chunk": {
                    "type": "string",
                    "description": "The ID/key of this particular lesson chunk",
                },                
                },
                "required": ["prompt","lesson_chunk"],
            },
            }
        },
        {
            "type": "function",
            "function": {
            "name": "assess_lesson_content",
            "description": "Requests another LLM to generate an assessment of the content as per your instructions. It will be provided the full lesson content automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                "system_prompt": {
                    "type": "string",
                    "description": "This describes what criteria and other constraints the LLM should use to provide its evaluation of the lesson content. Remember that the current lesson content will be provided automatically.",
                },                
                },
                "required": ["system_prompt"],
            },
            }
        },
        # {
        #     "type": "function",
        #     "function": {
        #     "name": "complete_lesson_generation",
        #     "description": "If the assessor LLM tells you the all lesson content and chunks are good, you will call this function to submit the lesson content. Use this ONLY when ALL lesson chunks are finalized to satisfaction.",
        #     "parameters": {
        #         "type": "object",
        #         "properties": {
        #         "complete_reason": {
        #             "type": "string",
        #             "description": "Simply state that the full lesson was approved and tell how many re-evaluations it took.",
        #         },                
        #         },
        #         "required": ["complete_reason"],
        #     },
        #     }
        # },
        
    ]

    # lesson_data = course_plan["chapters"][chapter]['lessons'][lesson]

    completed = False
    messages = []
    while not completed:
        output = call_model(system_prompt,
        prompt = f"Please proceed.",
        messages = messages,
        tools=tools)
        # print(output['content'])
        messages.append(output)
        if 'tool_calls' in output:
            completed = False
            for tool_call in output['tool_calls']:
                args = json.loads(tool_call['function']['arguments'])
                if tool_call['function']['name'] == 'generate_lesson_content':
                    tool_result = generate_lesson_content(**args)
                elif tool_call['function']['name'] == 'assess_lesson_content':
                    tool_result = assess_lesson_content(**args)['content']
                elif tool_call['function']['name'] == 'complete_lesson_generation':
                    completed = True
                    break
                messages.append({
                    "role": "tool",
                    "content": tool_result,
                    "tool_call_id": tool_call['id']
                })
        else:
            completed = True            
    return lesson_chunks


def generate_lesson_content(prompt,lesson_chunk):
    global lesson_chunks
    global generation_counts

    lesson_content_schema = {
        "type": "object",
        "properties": {
            "lesson_content": {
                "type": "string",
                "description": "The lesson content"
            },
            # "lesson_chunk": {
            #     "type": "string",
            #     "description": "The identifier for the lesson chunk. This will be provided by the user."
            # }
        },
        "required": ["lesson_content"]#, "lesson_chunk"]
    }
    
    system_prompt = f'''
        You are an expert educator. Generate a portion of a lesson based on the instructions/topic the user provides you.
        In some cases, you may be asked to modify an existing portion of a lesson with some feedback. If that is the case,
        this is the existing section of that lesson: 

        ```
        {lesson_chunks.get(lesson_chunk,'')}
        ```

        Make sure to just output the lesson content, no additional niceties or metadata.
    '''
    try:
        lesson_gen_output = call_model(system_prompt, prompt)['content']        
        lesson_chunks[lesson_chunk] = lesson_gen_output #['lesson_content']
        generation_counts[lesson_chunk] = generation_counts.get(lesson_chunk, 0) + 1
        return f"Sucessfully generated content for chunk {lesson_chunk} and saved it, please call the assessor. The total word count of the lesson is {len(" ".join(lesson_chunks.values()))}"
    except Exception as e:
        print(e)
        return f"Error generating lesson content: {e}"

def assess_lesson_content(system_prompt):   
    global lesson_chunks
    lesson_assessment_schema = {
        "type": "object",
        "properties": {            
            "feedback": {
                "type": "string",
                "description": "The feedback of the lesson content."
            },
            "approved": {
                "type": "boolean",
                "description": "Whether the lesson content is approved."
            }
        },
        "required": ["approved", "feedback"]
    }
    
    return call_model(system_prompt, json.dumps(lesson_chunks))