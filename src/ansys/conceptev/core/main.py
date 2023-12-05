# A Simple API Client for ConceptEV
import os
import dotenv
import httpx
import warnings
import datetime
import time
import plotly.graph_objects as go
from typing import Literal
from json import JSONDecodeError

dotenv.load_dotenv()

# Warning as this is not automated so changes to the API will cause changes here.
warnings.warn("Warning: The API is in rapidly changing state and this may become "
              "out of date very quickly.")

Router = Literal[
    "/architectures",
    "/components",
    "/components:from_file",
    "/components:calculate_loss_map",
    "/configurations",
    "/configurations:calculate_forces",
    "/requirements",
    "/requirements:calculate_examples",
    "/jobs",
    "/jobs:start",
    "/jobs:status",
    "/jobs:result",
    "/concepts",
    "/drive_cycles",
    "/drive_cycles:from_file",
    "/health",
]



def get_token() -> str:

    username = os.environ["CONCEPTEV_USERNAME"]
    password = os.environ["CONCEPTEV_PASSWORD"]
    ocm_url = os.environ["OCM_URL"]
    response = httpx.post(url=ocm_url + "/auth/login/",
                          json={"emailAddress": username, "password": password})
    if response.status_code != 200:
        raise Exception(f"Failed to get token {response.content}")
    return response.json()['accessToken']


def get_http_client(token: str, concept_id: str | None = None) -> httpx.Client:
    base_url = os.environ['CONCEPTEV_URL']
    if concept_id:
        params = {"concept_id": concept_id}
    else:
        params = None
    return httpx.Client(headers={"Authorization": token}, params=params,
                        base_url=base_url)

def processed_response(response) -> dict:
    if response.status_code == 200 or response.status_code == 201: #Success
        try:
            return response.json()
        except JSONDecodeError:
            return response.content
    raise Exception(f"Response Failed:{response}")


def get(client: httpx.Client, router: Router, id: str | None = None,
        params: dict | None = None) -> dict:
    if id:
        path = '/'.join([router, id])
    else:
        path = router
    response = client.get(url=path, params=params)
    return processed_response(response)

def post(client: httpx.Client, router: Router, data: dict) -> dict:
    response = client.post(url=router, json=data)
    return processed_response(response)

def read_file(filename: str) -> str:
    with open(filename) as f:
        content = f.read()
    return content

def read_results(client, job_info: dict, no_of_tries: int = 100, rate_limit: float = 0.3) -> dict:
    time_used = 0
    response = client.post(url='/jobs:result', json=job_info)
    for i in range(0,no_of_tries):
        response = client.post(url='/jobs:result', json=job_info)
        time_used += rate_limit
        time.sleep(rate_limit)
        if response.status_code == 200:
            return response.json()
    raise Exception(f"To many request tries: {response}")

def post_file(client: httpx.Client, router: Router, filename: str, params: dict) -> dict:
    path = ':'.join([router, 'from_file'])
    file_contents = read_file(filename)
    response = client.post(url=path, files={"file": file_contents}, params=params)
    return processed_response(response)

aero = {"name": "New Aero Config",
        "drag_coefficient": 1,
        "cross_sectional_area": 2,
        "config_type": "aero"}

if __name__ == '__main__':
    token = get_token()

    ## Check health of api connection and get a list of concepts
    with get_http_client(token) as client:
        health = get(client, "/health")
        print(health)
        concepts = get(client, "/concepts")
        print(concepts)
    concept_id = "655798edd85eed4a39fcaf18"  # Think this old concept might be corrupted.

    ## Add and create configs and component.
    with get_http_client(token, concept_id) as client:
        configurations = get(client, '/configurations', params={'config_type': 'aero'})
        print(configurations)
        created_aero = post(client, '/configurations', data=aero)
        print(created_aero)
        aero = get(client, "/configurations", id=created_aero['id'])
        print(aero)
        e9_lab_filename = 'e9.lab'
        created_motor = post_file(client, "/components", e9_lab_filename,
                             {"component_name": "e9",
                              "component_file_type": "motor_lab_file"})
        print(created_motor)
    ## Already made project run it.
    concept_id = "656eec2dd98cd6780c75f4b7"
    with get_http_client(token, concept_id) as client:
        # response = get(client,"requirements") # think this end point might be broken in test
        # print(response.content)
        concept = get(client, "/concepts", id="daf162d3-eba5-46d8-8b09-84970639dbfe",
                       params={"populated": True})
        job_input = {
            "job_name": "cli_job: " + datetime.datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S.%f"),
            "requirement_ids": concept['requirements_ids'],
            "architecture_id": concept['architecture_id'],
            "concept_id": concept['id'],
            "design_instance_id": concept['design_instance_id'],
        }
        job, uploaded_file = post(client, '/jobs', data=job_input)
        account_id = "93ec06dd-b43e-4e27-bdca-1a26474ee6f4"
        hpc_id = "dd5dd1a7-cc2e-4366-a7f1-c37b6f06f644"
        job_start = {
            "job": job,
            "uploaded_file": uploaded_file,
            "account_id": account_id,
            "hpc_id": hpc_id,
        }
        job_info = post(client, '/jobs:start', data=job_start)
        results = read_results(client,job_info)

        x = results[0]['capability_curve']['speeds']
        y = results[0]['capability_curve']['torques']

        fig = go.Figure(data=go.Scatter(x=x, y=y))
        fig.show()
