# Sourcetypes

The different sourcetypes used by the application provide a corresponding type of information:

- nifi:log:app
- nifi:log:bootstrap

It contains the record of all the activities of the NIFI application, from file uploads to execution times or bulletins found by the components.

- nifi:log:user

It contains the record of web activity where users interact and the actions they carry out.

- nifi:api:flow_status

It has the basic information related to the status and processing of the NIFI application

- nifi:api:site_to_site

Provides all the necessary information about the application to communicate with other instances.

- nifi:api:system_diagostics

It has the information about the system resources in use and available that the NIFI instance has.

- nifi:reporting:task  

Corresponds to internal reports of status metrics and operation of the application at a more detailed level with respect to flow status.

- nifi:reporting:bulletin

Provides information on the internal bulletins of the application where errors occurred during its operation are specified.