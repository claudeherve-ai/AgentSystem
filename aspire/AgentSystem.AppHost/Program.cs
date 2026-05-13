using Projects;

var builder = DistributedApplication.CreateBuilder(args);

// External Services (Azure OpenAI, GitHub, etc.) handled via Env
var azureOpenAi = builder.AddParameter("AzureOpenAIEndpoint", secret: true);
var azureApiKey = builder.AddParameter("AzureOpenAIApiKey", secret: true);

// The Core Agent System
var agents = builder.AddPythonProject("agents", "../../", "main.py")
    .WithEnvironment("AZURE_OPENAI_ENDPOINT", azureOpenAi)
    .WithEnvironment("AZURE_OPENAI_API_KEY", azureApiKey)
    .WithExternalHttpEndpoints();

// Monitoring Dashboard
var dashboard = builder.AddPythonProject("dashboard", "../../", "dashboard.py")
    .WithReference(agents)
    .WithExternalHttpEndpoints();

builder.Build().Run();
