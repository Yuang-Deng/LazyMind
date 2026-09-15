import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Form, Input, List, Select, Space, Spin, Typography } from "antd";
import { useTranslation } from "react-i18next";
import {
  createLocalDirectoryGrant,
  deleteLocalDirectoryGrant,
  listLocalDirectoryGrants,
  type LocalDirectoryGrant,
} from "../api/localDirectoryGrants";
import { markCloudDocumentConnectionSuccess } from "../utils/cloudDocumentOnboarding";

export default function LocalDirectoryGrants({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation();
  const [grants, setGrants] = useState<LocalDirectoryGrant[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<{ path: string; extensions: string[] }>();
  const refresh = useCallback(async () => {
    setLoading(true);
    setFailed(false);
    try { setGrants(await listLocalDirectoryGrants()); }
    catch { setFailed(true); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const add = async ({ path, extensions }: { path: string; extensions: string[] }) => {
    if (saving || !canManage) return;
    setSaving(true);
    try {
      const grant = await createLocalDirectoryGrant(path, extensions);
      setGrants((current) => [...current, grant]);
      form.resetFields(["path"]);
      markCloudDocumentConnectionSuccess("local");
    } catch { /* Shared request interceptor displays the server error. */ }
    finally { setSaving(false); }
  };
  const remove = async (id: string) => {
    if (saving || !canManage) return;
    setSaving(true);
    try {
      await deleteLocalDirectoryGrant(id);
      setGrants((current) => current.filter((grant) => grant.id !== id));
    } catch { /* Shared request interceptor displays the server error. */ }
    finally { setSaving(false); }
  };

  return (
    <div className="model-provider-cloud-doc-setting-card is-directory-config">
      <Typography.Title level={4}>{t("modelProvider.cloudDocuments.localReadTitle")}</Typography.Title>
      <Typography.Paragraph>{t("modelProvider.cloudDocuments.localReadHint")}</Typography.Paragraph>
      {failed ? (
        <Alert type="error" showIcon message={t("modelProvider.cloudDocuments.localChatDirectoriesLoadFailed")}
          action={<Button onClick={() => void refresh()}>{t("common.retry")}</Button>} />
      ) : (
        <Spin spinning={loading}>
          <List dataSource={grants} locale={{ emptyText: t("modelProvider.cloudDocuments.localReadEmpty") }}
            renderItem={(grant) => (
              <List.Item actions={canManage ? [
                <Button key="remove" danger disabled={saving || loading} onClick={() => void remove(grant.id)}>
                  {t("modelProvider.cloudDocuments.localReadRemove")}
                </Button>,
              ] : []}>
                <List.Item.Meta title={<span style={{ overflowWrap: "anywhere" }}>{grant.path}</span>}
                  description={(grant.file_extensions || []).map((ext) => `.${ext}`).join(", ")} />
              </List.Item>
            )} />
        </Spin>
      )}
      {canManage && (
        <Form form={form} layout="vertical" onFinish={(values: { path: string; extensions: string[] }) => void add(values)}
          initialValues={{ extensions: ["txt", "md", "pdf", "docx", "xlsx", "csv"] }}
          disabled={saving || loading || failed}>
          <Form.Item name="path" label={t("modelProvider.cloudDocuments.localReadPath")} rules={[{ required: true, whitespace: true }]}>
            <Input placeholder={t("modelProvider.cloudDocuments.localReadPathPlaceholder")} />
          </Form.Item>
          <Form.Item name="extensions" label={t("modelProvider.cloudDocuments.localReadExtensions")} rules={[{ required: true, type: "array", min: 1 }]}>
            <Select mode="tags" tokenSeparators={[",", " "]} open={false} />
          </Form.Item>
          <Space><Button htmlType="submit" type="primary" loading={saving}>
            {t("modelProvider.cloudDocuments.localReadAdd")}
          </Button></Space>
        </Form>
      )}
    </div>
  );
}
