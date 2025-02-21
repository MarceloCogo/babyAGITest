# *********HOW TO USE**********
# 1. Fork this into a private Repl
# 2. Add your OpenAI API Key and Pinecone API Key
# 3. Go to "Shell" (over to the right ->) and type "pip install pinecone-client" and press enter
# 4. Update the OBJECTIVE variable
# 5. Press "Run" at the top.
# NOTE: the first time you run, it will initiate the table first - which may take a few minutes, you'll be waiting at the initial OBJECTIVE phase. If it fails, try again.)
#
# WARNING: THIS CODE WILL KEEP RUNNING UNTIL YOU STOP IT. BE MINDFUL OF OPENAI API BILLS. DELETE PINECONE INDEX AFTER USE.


from pinecone import Pinecone
from pinecone import ServerlessSpec
from openai import OpenAI

import time
from collections import deque
from typing import Dict, List

#Set API Keys
OPENAI_API_KEY = "your_key"
PINECONE_API_KEY = "your_key"
PINECONE_ENVIRONMENT = "us-east1-gcp" #Pinecone Environment (eg. "us-east1-gcp")


#Set Variables
YOUR_TABLE_NAME = "test-table"
OBJECTIVE = "Resolver a fome do mundo"
YOUR_FIRST_TASK = "Desenvolva uma lista de tarefas."

#Print OBJECTIVE
print("\033[96m\033[1m"+"\n*****OBJECTIVE*****\n"+"\033[0m\033[0m")
print(OBJECTIVE)

# Configure OpenAI and Pinecone
#openai.api_key = OPENAI_API_KEY

client = OpenAI(
  api_key=OPENAI_API_KEY
)


pc = Pinecone(api_key=PINECONE_API_KEY)
#pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENVIRONMENT)

# Create Pinecone index
table_name = YOUR_TABLE_NAME
dimension = 1536
metric = "cosine"
pod_type = "p1"

#print(pc.list_indexes())
existing_indexes = [index['name'] for index in pc.list_indexes()]

if table_name not in existing_indexes:
    pc.create_index(name=table_name, dimension=dimension, metric=metric, spec=ServerlessSpec(
        cloud='aws',
        region='us-east-1'
    ))

# Connect to the index
index = pc.Index(table_name)

# Task list
task_list = deque([])

def add_task(task: Dict):
    task_list.append(task)

def get_ada_embedding(text):
    text = text.replace("\n", " ")
    #return client.Embedding.create(input=[text], model="text-embedding-ada-002")["data"][0]["embedding"]
    return client.embeddings.create(input = [text], model="text-embedding-ada-002").data[0].embedding


def task_creation_agent(objective: str, result: Dict, task_description: str, task_list: List[str]):
    messages = [
        {"role": "system", "content": "You are an AI who performs one task based on the following objective."},
        {"role": "user", "content": f"You are a task creation AI that uses the result of an execution agent to create new tasks with the following objective: {objective}. The last completed task has the result: {result}. This result was based on this task description: {task_description}. These are incomplete tasks: {', '.join(task_list)}. Based on the result, create new tasks to be completed by the AI system that do not overlap with incomplete tasks. Return the tasks as an array. Escreva em português."}
    ]
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.5,
        max_tokens=100,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )
    
    new_tasks = response.choices[0].message.content.strip().split('\n')
    return [{"task_name": task_name} for task_name in new_tasks]


def prioritization_agent(this_task_id: int):
    global task_list
    task_names = [t["task_name"] for t in task_list]
    next_task_id = int(this_task_id) + 1
    messages = [
        {"role": "system", "content": "You are an AI who performs one task based on the following objective."},
        {"role": "user", "content": f"You are an task prioritization AI tasked with cleaning the formatting of and reprioritizing the following tasks: {task_names}. Consider the ultimate objective of your team: {OBJECTIVE}. Do not remove any tasks. Return the result as a numbered list, like:\n#. First task\n#. Second task\nStart the task list with number. Escreva em português. Se limite a 3 {next_task_id}."}
    ]
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.5,

    )
    
    new_tasks = response.choices[0].message.content.strip().split('\n')
    task_list = deque()
    for task_string in new_tasks:
        task_parts = task_string.strip().split(".", 1)
        if len(task_parts) == 2:
            task_id = task_parts[0].strip()
            task_name = task_parts[1].strip()
            task_list.append({"task_id": task_id, "task_name": task_name})




def execution_agent(objective:str,task: str) -> str:
    context=context_agent(index=YOUR_TABLE_NAME, query=objective, n=5)
    response = client.chat.completions.create(
    model="gpt-4o-mini",  # Modelo de chat
        messages=[
            {"role": "system", "content": "You are an AI who performs one task based on the following objective. Escreva em português"},
            {"role": "user", "content": f"Objective: {objective}. Task: {task}. Context: {context}"}
        ],
        temperature=0.7   
)
    
    return response.choices[0].message.content.strip()

  

def context_agent(query: str, index: str, n: int):
    query_embedding = get_ada_embedding(query)
    index = pc.Index(YOUR_TABLE_NAME)
    results = index.query(vector=query_embedding, top_k=n,
    include_metadata=True)

    #print("***** RESULTS *****")
    #print(results)
    sorted_results = sorted(results.matches, key=lambda x: x.score, reverse=True)    
    return [(str(item.metadata['task'])) for item in sorted_results]

# Add the first task
first_task = {
    "task_id": 1,
    "task_name": YOUR_FIRST_TASK
}

add_task(first_task)
# Main loop
task_id_counter = 1
while True:
    if task_list:
        # Print the task list
        print("\033[95m\033[1m"+"\n*****TASK LIST*****\n"+"\033[0m\033[0m")
        for t in task_list:
            print(str(t['task_id'])+": "+t['task_name'])

        # Step 1: Pull the first task
        task = task_list.popleft()
        print("\033[92m\033[1m"+"\n*****NEXT TASK*****\n"+"\033[0m\033[0m")
        print(str(task['task_id'])+": "+task['task_name'])

        # Send to execution function to complete the task based on the context
        result = execution_agent(OBJECTIVE,task["task_name"])
        this_task_id = int(task["task_id"])
        print("\033[93m\033[1m"+"\n*****TASK RESULT*****\n"+"\033[0m\033[0m")
        print(result)

        # Step 2: Enrich result and store in Pinecone
        enriched_result = {'data': result}  # This is where you should enrich the result if needed
        result_id = f"result_{task['task_id']}"
        vector = enriched_result['data']  # extract the actual result from the dictionary
        index.upsert([(result_id, get_ada_embedding(vector),{"task":task['task_name'],"result":result})])

    # Step 3: Create new tasks and reprioritize task list
    new_tasks = task_creation_agent(OBJECTIVE,enriched_result, task["task_name"], [t["task_name"] for t in task_list])

    for new_task in new_tasks:
        task_id_counter += 1
        new_task.update({"task_id": task_id_counter})
        add_task(new_task)
    prioritization_agent(this_task_id)

time.sleep(1)  # Sleep before checking the task list again