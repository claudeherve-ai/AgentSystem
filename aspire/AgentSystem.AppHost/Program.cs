using Aspire.Hosting;
using Aspire.Hosting.ApplicationModel;
using AgentSystem.ServiceDefaults;
using AgentSystem.AppHost;

// Auto-detect virtual environment path
var venvPath = OperatingSystem.IsWindows()
    ? @"C:\Users\tedch\AgentSystem\.venv"
    : "/mnt/c/Users/tedch/AgentSystem/.venv-wsl";

var builder = DistributedApplication.CreateBuilder(args);

// ── Secrets & Configuration ──────────────────────────────────────────────
var azureOpenAi = builder.AddParameter("AzureOpenAIEndpoint", secret: true);
var azureApiKey = builder.AddParameter("AzureOpenAIApiKey", secret: true);
var graphClientId = builder.AddParameter("GraphClientId", secret: false);

// ── AgentSystem FastAPI Backend ──────────────────────────────────────────
var api = builder.AddPythonProject("api", "../../", "api/main.py", virtualEnvironmentPath: venvPath)
    .WithEnvironment("AZURE_OPENAI_ENDPOINT", azureOpenAi)
    .WithEnvironment("AZURE_OPENAI_API_KEY", azureApiKey)
    .WithEnvironment("GRAPH_CLIENT_ID", graphClientId)
    .WithEnvironment("PYTHONPATH", "../../")
    .WithEnvironment("AGENTSYSTEM_MODE", "api")
    .WithEnvironment("AGENTSYSTEM_AUTH_ENABLED", "true")
    .WithEndpoint("http", endpoint => { endpoint.Port = 8080; endpoint.IsExternal = true; });

// ── AgentSystem Streamlit Dashboard ──────────────────────────────────────
var dashboard = builder.AddPythonProject("dashboard", "../../", "dashboard.py", virtualEnvironmentPath: venvPath)
    .WithReference(api)
    .WithEnvironment("AZURE_OPENAI_ENDPOINT", azureOpenAi)
    .WithEnvironment("AZURE_OPENAI_API_KEY", azureApiKey)
    .WithEnvironment("GRAPH_CLIENT_ID", graphClientId)
    .WithEnvironment("PYTHONPATH", "../../")
    .WithEnvironment("AGENTSYSTEM_API_URL", "http://api:8080")
    .WithEndpoint("http", endpoint => { endpoint.Port = 8501; endpoint.IsExternal = true; });

builder.Build().Run();
