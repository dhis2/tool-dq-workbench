Configuration
============================

Server configuration
----------------------------
The server configuration is specified in a YAML file. A sample configuration file is provided in the `config` directory of the repository. You should copy this file to a directory of your choice and modify it as needed.
Here is an example of the server configuration:


.. code-block:: yaml

   server:
   # replace with your DHIS2 instance URL/No trailing slash
     base_url: https://play.im.dhis2.org/stable-2-42-1 
     d2_token: YOUR_API_TOKEN
     logging_level: INFO            # DEBUG | INFO | WARNING | ERROR
     max_concurrent_requests: 10    # limits simultaneous API calls
     max_results: 1000              # caps results per request (500–50000)


Creating a dedicated user account
----------------------------------


Ideally, you should use a dedicated user account with an API token for authentication which has a limited set of permissions. These permissions include:
 - Add data element groups
 - Add data elements
 - Export metadata
 - Import metadata
 - Add/update min-max data values
 - Add/update data values
 - Run validation
 - Perform maintenance tasks

 Keep in mind that if any of your data sets are restricted by user groups, you will need to ensure that the user account you are using
 for the DQ Workbench tool is a member of those user groups so that ithas access
 to read data from those data sets. The user should also be assigned to the root organisation unit to ensure full access to all data across
 the organisation unit hierarchy.

Once you have created the user account, login with that account and generate an API token. 
This token will be used for authentication when the DQ Workbench tool interacts with the DHIS2 instance.
You will need to grant the copy at least "GET" and "POST" permissions.
You should carefully consider the expiry date for the token. 
It is best security practice to set an expiry date and renew the token before it expires.
However, if you set an expiry date, you will need to remember to update the configuration file with the new token before the old one expires to avoid disruptions in service.

You can generate an API token by navigating to the user profile page in DHIS2 and selecting the "Generate new token" option.
Be sure to keep your browser tab open until you have copied the token, as you will not be able to retrieve it again later.
Once you have copied the token, paste it into the `d2_token` field in your configuration file or enter it in the web UI configuration page.


Sample configuration file (UI view)
----------------------------
.. image:: _static/screenshots/server_config.png
   :alt: Server configuration
   :width: 80%
   :align: center
