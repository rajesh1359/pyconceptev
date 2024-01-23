..
   Just reuse the root readme to avoid duplicating the documentation.
   Provide any documentation specific to your online documentation
   here.

.. include:: ../../README.rst


ConceptEV Specific Instructions
-------------
.. WARNING::
   Beware this api is in a state of rapid to change and should be considered unstable.


You need to:
- `Configure Session using .env file`
- `Get a token`
- `Create a client`
- `Understand the API` at https://dev-conceptev.awsansys3np.onscale.com/api/docs


Configure Session using .env file
^^^^^^^^^^^^

you need to create a .env file to keep your password and other configurable data it should look something like this:
.. code-block:: bash
    CONCEPTEV_USERNAME = joe.blogs@my_work.com
    CONCEPTEV_PASSWORD = sup3r_s3cr3t_passw0rd
    OCM_URL = https://test.portal.onscale.com/api
    CONCEPTEV_URL = https://dev-conceptev.awsansys3np.onscale.com/api


Get a token
^^^^^^^^^^^

Import the main module and use get_token this should return a random string from the servers to get you access.

.. code-block:: python
    import pyconceptev-core.main as pyconceptev #Test this
    token = pyconceptev.get_token()


Create a client
^^^^^^^^^^^^^^^

You need to create a client that can access and talk to the api. You can use the health check api to check your connection.

.. code-block:: python
    import pythonconceptev-core.main as pyconceptev

    with pyconceptev.create_client(token,concept_id) as client:
        print(pyconceptev.read(client,"/health"))

Understand the API
^^^^^^^^^^^^^^^^^^

Use the api documentation at https://dev-conceptev.awsansys3np.onscale.com/api/docs
This shows you which verbs and which routes/paths are available and what inputs/outputs they have.
You can use the verb functions created in this module to make things simpler.

To create a configuration we need to use the verb `post` with route `/configurations` and add the `data` from the schema.
.. code-block:: python
    pyconcetpev.create(client,'/configurations',data={"name": "New Aero Config",
                                                        "drag_coefficient": 1,
                                                        "cross_sectional_area": 2,
                                                        "config_type": "aero"})

