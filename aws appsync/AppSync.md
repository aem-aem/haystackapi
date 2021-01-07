# Use AWS AppSync

With AWS AppSync, it's possible to merge the Haystack GraphQL API with another GraphQL API.

## Schema

The current GraphQL schema for Hystack is [here](../schema.graphql)

## Delegate part of global GraphQL to haystack GraphQL API

This sample help demonstrate how it's possible to delegate a part of GraphQL request to Haystack GraphQL API with AWS
AppSync.

In the AWS AppSync console:

* First, deploy you AWS Lambda function with Haystack GraphQL API
* Build from scratch a new API with the name `HaystackAPI`
* Create a datasource `HaystackLambda` with an AWS Lambda function
  - Select "Lambda Function"
  - Select the AWS Lambda for Haystack
  - Select the region
  - and a role

![alt New Data Source][newDataSource]

* Create a function
  - Choose the data source `HaystackAPILambda`
  - Function name `HaystackAPIWrapper`
  - Description `Delegate part of Graphql request to Haystack GraphQL API`
  - import the body of [`request-filter.json`](request-filter.json) inside the
    `Configure the request mapping template`
  - import the body of [`response-filter.json`](response-filter.json) inside the
    `Configure the response mapping template`
  - ask the API URL (`zappa status --json | jq -r '."API Gateway URL"'`).
  - You must receive something like `https://jihndyzv6h.execute-api.us-east-2.amazonaws.com/dev`. Extract only the host
    name.
  - Inside the request filter:
    - The prefix must be set in the variable `$apiId` (`#set($apiId = "jihndyzv6h"))
    - Update the variable `$region` (`#set($region = "us-east-2")`)

![alt New Data Source][newFunction]

* Import the schema
  - Copy the body of [`schema.graphql`](../schema.graphql) in the schema of AppSync
  - Save the schema
  - Add the end of the Resolver list, attach a resolver for the filed `haystack`

![alt Attach Resolver][attachResolver]

- select the datasource `HaystackAPILambda`
- Convert to pipeline resolver and add the function `HaystackAPIWrapper`
- Create and save the resolver

![alt Create Pipeline Resolver][createPipelineResolver]

* Test a query
  - like `{ haystack { tagValues(tag:"dis") } }`

![alt Query][query]

Now, you can **extend** the AppSync schema and attach others API in the endpoint.

[newDataSource]: New_Data_Source.png "New Data Source"

[newFunction]: New_Function.png "New Function"

[attachResolver]: Attach_Resolver.png "Attach Resolver"

[createPipelineResolver]: Create_Pipeline_Resolver.png "Create Pipeline resolver"

[query]: Queries.png "Query"