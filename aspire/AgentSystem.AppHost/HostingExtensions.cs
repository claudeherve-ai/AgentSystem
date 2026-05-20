using Aspire.Hosting;
using Aspire.Hosting.ApplicationModel;

namespace AgentSystem.AppHost;

public static class HostingExtensions
{
    /// <summary>
    /// Marks the first HTTP endpoint of a resource as externally accessible.
    /// </summary>
    public static IResourceBuilder<T> WithExternalHttpEndpoints<T>(this IResourceBuilder<T> builder)
        where T : IResourceWithEndpoints
    {
        return builder.WithEndpoint("http", endpoint =>
        {
            endpoint.IsExternal = true;
        });
    }
}
