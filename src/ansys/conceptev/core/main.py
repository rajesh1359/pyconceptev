"""A Simple API Client for ConceptEV."""
import datetime
from json import JSONDecodeError
import os
from pathlib import Path
import time
from typing import Literal
import warnings

import dotenv
import httpx
import plotly.graph_objects as go

DATADIR = Path(__file__).parents[0]

dotenv.load_dotenv()

# Warning as this is not automated so changes to the API will cause changes here.
warnings.warn(
    "Warning: The API is in rapidly changing state and this may become " "out of date very quickly."
)

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
    """Get Token from OCM."""
    username = os.environ["CONCEPTEV_USERNAME"]
    password = os.environ["CONCEPTEV_PASSWORD"]
    ocm_url = os.environ["OCM_URL"]
    response = httpx.post(
        url=ocm_url + "/auth/login/", json={"emailAddress": username, "password": password}
    )
    if response.status_code != 200:
        raise Exception(f"Failed to get token {response.content}")
    return response.json()["accessToken"]


def get_http_client(token: str, design_instance_id: str | None = None) -> httpx.Client:
    """Get a http client.

    This http client creates and maintains the connection and is more performant than
    re-creating that connection for each call.
    """
    base_url = os.environ["CONCEPTEV_URL"]
    if design_instance_id:
        params = {"design_instance_id": design_instance_id}
    else:
        params = None
    return httpx.Client(headers={"Authorization": token}, params=params, base_url=base_url)


def processed_response(response) -> dict:
    """Process response.

    Check the return from the api and if it's not successful raise an error.
    """
    if response.status_code == 200 or response.status_code == 201:  # Success
        try:
            return response.json()
        except JSONDecodeError:
            return response.content
    raise Exception(f"Response Failed:{response}")


def get(
    client: httpx.Client, router: Router, id: str | None = None, params: dict | None = None
) -> dict:
    """Get/read from the client at the specific route.

    A http verb. Performs the get request adding the route to the base client.
    """
    if id:
        path = "/".join([router, id])
    else:
        path = router
    response = client.get(url=path, params=params)
    return processed_response(response)


def post(client: httpx.Client, router: Router, data: dict, params: dict = {}) -> dict:
    """Post/create from the client at the specific route.

    A http verb. Performs the post request adding the route to the base client.
    """
    response = client.post(url=router, json=data, params=params)
    return processed_response(response)


def delete(client: httpx.Client, router: Router, id: str) -> dict:
    """Delete from the client at the specific route.

    A http verb. Performs the delete request adding the route to the base client.
    """
    path = "/".join([router, id])
    response = client.delete(url=path)
    if response.status_code != 204:
        raise Exception(f"Failed to delete from {router} with id:{id}")


def create_new_project(
    client: httpx.Client,
    account_id: str,
    hpc_id: str,
    title: str,
    project_goal: str = "Created from the CLI",
):
    """Create a new project."""
    osm_url = os.environ["OCM_URL"]
    token = client.headers["Authorization"]
    project_data = {
        "accountId": account_id,
        "hpcId": hpc_id,
        "projectTitle": title,
        "projectGoal": project_goal,
    }
    created_project = httpx.post(
        osm_url + "/project/create", headers={"Authorization": token}, json=project_data
    )
    if created_project.status_code != 200 and created_project.status_code != 204:
        raise Exception(f"Failed to create a project on OCM {created_project}")

    design_data = {
        "projectId": created_project.json()["projectId"],
        "productId": "ec987729-a125-4f9d-ae3f-c3a81ca75112",
        "designTitle": "Branch 1",
    }
    created_design = httpx.post(
        osm_url + "/design/create", headers={"Authorization": token}, json=design_data
    )

    if created_design.status_code != 200 and created_design.status_code != 204:
        raise Exception(f"Failed to create a design on OCM {created_design}")

    user_details = httpx.post(osm_url + "/user/details", headers={"Authorization": token})
    if user_details.status_code != 200 and user_details.status_code != 204:
        raise Exception(f"Failed to get a user details on OCM {user_details}")

    concept_data = {
        "capabilities_ids": [],
        "components_ids": [],
        "configurations_ids": [],
        "design_id": created_design.json()["designId"],
        "design_instance_id": created_design.json()["designInstanceList"][0]["designInstanceId"],
        "drive_cycles_ids": [],
        "jobs_ids": [],
        "name": "Branch 1",
        "project_id": created_project.json()["projectId"],
        "requirements_ids": [],
        "user_id": user_details.json()["userId"],
    }

    created_concept = post(client, "/concepts", data=concept_data)
    return created_concept


def get_concept_ids(client: httpx.Client):
    """Get Concept Ids."""
    concepts = get(client, "/concepts")
    return {concept["name"]: concept["id"] for concept in concepts}


def get_account_ids(token: str) -> dict:
    """Get account ids."""
    ocm_url = os.environ["OCM_URL"]
    response = httpx.post(url=ocm_url + "/account/list", headers={"authorization": token})
    if response.status_code != 200:
        raise Exception(f"Failed to get accounts {response}")
    accounts = {
        account["account"]["accountName"]: account["account"]["accountId"]
        for account in response.json()
    }
    return accounts


def get_default_hpc(token: str, account_id: str):
    """Get default hpc id."""
    ocm_url = os.environ["OCM_URL"]
    response = httpx.post(
        url=ocm_url + "/account/hpc/default",
        json={"accountId": account_id},
        headers={"authorization": token},
    )
    if response.status_code != 200:
        raise Exception(f"Failed to get accounts {response}")
    return response.json()["hpcId"]


def create_submit_job(
    client,
    concept: dict,
    account_id: str,
    hpc_id: str,
    job_name: str = "cli_job: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
):
    """Create and then submit a job."""
    job_input = {
        "job_name": job_name,
        "requirement_ids": concept["requirements_ids"],
        "architecture_id": concept["architecture_id"],
        "concept_id": concept["id"],
        "design_instance_id": concept["design_instance_id"],
    }
    job, uploaded_file = post(client, "/jobs", data=job_input)
    job_start = {
        "job": job,
        "uploaded_file": uploaded_file,
        "account_id": account_id,
        "hpc_id": hpc_id,
    }
    job_info = post(client, "/jobs:start", data=job_start)
    return job_info


def put(client: httpx.Client, router: Router, id: str, data: dict) -> dict:
    """Put/update from the client at the specific route.

    A http verb. Performs the put request adding the route to the base client.
    """
    path = "/".join([router, id])
    response = client.put(url=path, json=data)
    return processed_response(response)


def read_file(filename: str) -> str:
    """Read file."""
    with open(filename) as f:
        content = f.read()
    return content


def read_results(client, job_info: dict, no_of_tries: int = 100, rate_limit: float = 0.3) -> dict:
    """Keep trying for results if the results aren't completed try again."""
    for i in range(0, no_of_tries):
        response = client.post(url="/jobs:result", json=job_info)
        time.sleep(rate_limit)
        if response.status_code == 200:
            return response.json()

    raise Exception(f"To many request: {response}")


def post_file(client: httpx.Client, router: Router, filename: str, params: dict) -> dict:
    """Post/create from the client at the specific route with a file.

    A http verb. Performs the post request adding the route to the base client.
    Adds the file as a multipart form request.
    """
    path = ":".join([router, "from_file"])
    file_contents = read_file(filename)
    response = client.post(url=path, files={"file": file_contents}, params=params)
    return processed_response(response)


# Example data can be got from the schema sections of the api docs.

aero = {
    "name": "New Aero Config",
    "drag_coefficient": 0.3,
    "cross_sectional_area": 2,
    "config_type": "aero",
}

aero2 = {
    "name": "Second Aero Configuration",
    "drag_coefficient": 0.6,
    "cross_sectional_area": 3,
    "config_type": "aero",
}
mass = {
    "name": "New Mass Config",
    "mass": 3000,
    "config_type": "mass",
}

wheel = {
    "name": "New Wheel Config",
    "rolling_radius": 0.3,
    "config_type": "wheel",
}

transmission = {
    "gear_ratios": [5],
    "headline_efficiencies": [0.95],
    "max_torque": 500,
    "max_speed": 2000,
    "static_drags": [0.5],
    "friction_ratios": [60],
    "windage_ratios": [40],
    "component_type": "TransmissionLossCoefficients",
}

motor_file_name = str(DATADIR.joinpath("e9.lab"))
motor_params = {"component_name": "e9", "component_file_type": "motor_lab_file"}

battery = {
    "capacity": 86400000,
    "charge_acceptance_limit": 0,
    "component_type": "BatteryFixedVoltages",
    "internal_resistance": 0.1,
    "name": "New Battery",
    "voltage_max": 400,
    "voltage_mid": 350,
    "voltage_min": 300,
}

if __name__ == "__main__":
    token = get_token()

    with get_http_client(token) as client:  # Create a client to talk to the api
        health = get(client, "/health")  # Check the api is healthy
        print(health)
        concepts = get(client, "/concepts")  # Get a list of concepts
        print(concepts)

        accounts = get_account_ids(token)
        account_id = accounts["conceptev_saas@ansys.com"]
        hpc_id = get_default_hpc(token, account_id)
        created_concept = create_new_project(
            client, account_id, hpc_id, f"New Project +{datetime.datetime.now()}"
        )  # Create a new concept.

    concept_id = created_concept["id"]  # get the id of the newly created concept.
    design_instance_id = created_concept["design_instance_id"]
    with get_http_client(token, concept_id) as client:  # get client with concept id embedded in
        ### Basic Post(create) and get(read) operations on Configurations
        created_aero = post(client, "/configurations", data=aero)  # create an aero
        created_aero2 = post(client, "/configurations", data=aero2)  # create an aero
        created_mass = post(client, "/configurations", data=mass)
        created_wheel = post(client, "/configurations", data=wheel)

        configurations = get(
            client, "/configurations", params={"config_type": "aero"}
        )  # read all aeros
        print(configurations)

        aero = get(
            client, "/configurations", id=created_aero["id"]
        )  # get a particular aero configuration
        print(aero)

        ### Create Components
        created_transmission = post(client, "/components", data=transmission)  # create transmission

        created_motor = post_file(
            client, "/components", motor_file_name, params=motor_params  # create motor from file
        )
        print(created_motor)
        client.timeout = 2000  # Needed as these calculations will take a long time.
        motor_loss_map = post(
            client,
            "/components:calculate_loss_map",
            data={},
            params={"component_id": created_motor["id"]},
        )  # get loss map from motor

        x = motor_loss_map["currents"]
        y = motor_loss_map["phase_advances"]
        z = motor_loss_map["losses_total"]
        fig = go.Figure(data=go.Contour(x=x, y=y, z=z))
        fig.show()

        created_battery = post(client, "/components", data=battery)  # create battery

        ### Architecture
        architecture = {
            "number_of_front_wheels": 1,
            "number_of_front_motors": 1,
            "front_transmission_id": created_transmission["id"],
            "front_motor_id": created_motor["id"],
            "number_of_rear_wheels": 0,
            "number_of_rear_motors": 0,
            "battery_id": created_battery["id"],
        }
        created_arch = post(client, "/architectures", data=architecture)  # create arch

        # Requirements
        requirement = {
            "speed": 10,
            "acceleration": 1,
            "aero_id": created_aero["id"],
            "mass_id": created_mass["id"],
            "wheel_id": created_wheel["id"],
            "state_of_charge": 0.9,
            "requirement_type": "static_acceleration",
            "name": "Static Requirement 1",
        }
        created_requirement = post(client, "requirements", data=requirement)

        ### Submit job
        concept = get(client, "/concepts", id=design_instance_id, params={"populated": True})

        job_info = create_submit_job(client, concept, account_id, hpc_id)

        ### Read results
        results = read_results(client, job_info)
        x = results[0]["capability_curve"]["speeds"]
        y = results[0]["capability_curve"]["torques"]

        time.sleep(120)  # Wait for the job to complete.
        fig = go.Figure(data=go.Scatter(x=x, y=y))
        fig.show()
