import { Configuration, DataSourcesApiFactory } from "@/api/generated/core-client";
import type { LocalDirectoryGrant, LocalDirectoryGrantsResponse } from "@/api/generated/core-client";
import { BASE_URL, axiosInstance } from "@/components/request";
import { unwrapApiData } from "@/modules/dataSource/api/unwrap";

export type { LocalDirectoryGrant } from "@/api/generated/core-client";

const basePath = BASE_URL || window.location.origin;
const api = DataSourcesApiFactory(new Configuration({ basePath }), basePath, axiosInstance);

export async function listLocalDirectoryGrants() {
  const response = await api.apiCoreDataSourcesLocalDirectoryGrantsGet();
  return unwrapApiData<LocalDirectoryGrantsResponse>(response.data).items || [];
}

export async function createLocalDirectoryGrant(path: string, fileExtensions: string[]) {
  const response = await api.apiCoreDataSourcesLocalDirectoryGrantsPost({
    localDirectoryGrantRequest: { path, file_extensions: fileExtensions },
  });
  return unwrapApiData<LocalDirectoryGrant>(response.data);
}

export async function deleteLocalDirectoryGrant(id: string) {
  await api.apiCoreDataSourcesLocalDirectoryGrantsGrantDelete({ grant: id });
}
