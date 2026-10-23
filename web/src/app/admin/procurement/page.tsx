"use client";

import { useState } from "react";
import useSWR from "swr";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { Button, InputTextArea, Text } from "@opal/components";
import { Section, SettingsLayouts } from "@opal/layouts";

const reviewSchema = z.object({
  id: z.string(), owner_id: z.string(), payload_hash: z.string(),
  state: z.enum(["draft", "submitted", "approved", "rejected"]), version: z.number(),
  payload: z.object({ vendor_ref: z.string(), tender_ref: z.string() }).passthrough(),
});
type Review = z.infer<typeof reviewSchema>;
const auditSchema = z.array(z.object({ actor_id: z.string(), action: z.string(), version: z.number(), payload_hash: z.string(), note: z.string() }));
const sample = {
  vendor_ref: "SYN-VENDOR-001", tender_ref: "SYN-TENDER-001",
  requirements: [{ key: "quality", label: "ISO quality certificate", mandatory: true }],
  evidence: [{ requirement_key: "quality", document_ref: "SYN-DOC-001", version: "v1",
    quote: "Synthetic certificate for a demonstration vendor.", valid_until: "2099-12-31T00:00:00Z" }],
};

async function request(url: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(url, { ...init, headers: { "Content-Type": "application/json", ...init.headers } });
  if (!response.ok) throw new Error(await response.text());
  return response;
}

async function fetchReviews(url: string): Promise<Review[]> {
  return z.array(reviewSchema).parse(await (await request(url)).json());
}

async function fetchAudit(url: string): Promise<z.infer<typeof auditSchema>> {
  return auditSchema.parse(await (await request(url)).json());
}

export default function ProcurementPage() {
  const t = useTranslations("procurement");
  const [raw, setRaw] = useState(JSON.stringify(sample, null, 2));
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const { data, error: loadError, isLoading, mutate } = useSWR("/api/admin/procurement", fetchReviews);
  const { data: audit, mutate: refreshAudit } = useSWR(selected ? `/api/admin/procurement/${selected}/audit` : null, fetchAudit);

  async function create(): Promise<void> {
    setBusy(true); setError("");
    try {
      const payload: unknown = JSON.parse(raw);
      await request("/api/admin/procurement", { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify(payload) });
      await mutate();
    } catch (failure) { setError(failure instanceof Error ? failure.message : t("failed")); }
    finally { setBusy(false); }
  }

  async function decide(review: Review, action: "submit" | "approve" | "reject"): Promise<void> {
    setBusy(true); setError("");
    try {
      await request(`/api/admin/procurement/${review.id}/decision`, { method: "POST", body: JSON.stringify({ version: review.version, action, note }) });
      await mutate(); await refreshAudit();
    } catch (failure) { setError(failure instanceof Error ? failure.message : t("failed")); }
    finally { setBusy(false); }
  }

  return <SettingsLayouts.Root width="lg">
    <SettingsLayouts.Header title={t("title")} description={t("description")} actions={[
      <Button key="refresh" prominence="secondary" onClick={() => void mutate()}>{t("refresh")}</Button>,
    ]} />
    <SettingsLayouts.Body>
      <Section height="auto" alignItems="stretch" gap={3}>
        <Text font="heading-h3">{t("newCase")}</Text>
        <Text color="text-03">{t("payloadHelp")}</Text>
        <InputTextArea aria-label={t("newCase")} mono rows={12} maxLength={200000} value={raw} onChange={(event) => setRaw(event.target.value)} />
        <Button disabled={busy} onClick={() => void create()}>{t("create")}</Button>
      </Section>
      <Section height="auto" alignItems="stretch" gap={3}>
        <Text>{t("reviewHint")}</Text>
        <InputTextArea aria-label={t("note")} placeholder={t("note")} rows={2} maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} />
        {(error || loadError) && <Text color="status-error-05">{error || t("failed")}</Text>}
        {isLoading && <Text>{t("loading")}</Text>}
        {data?.length === 0 && <Text>{t("empty")}</Text>}
        {data?.map((review) => <Section key={review.id} height="auto" alignItems="stretch" padding={4} gap={3} className="border border-02 rounded-lg">
          <Text font="main-content-emphasis">{`${review.payload.tender_ref} / ${review.payload.vendor_ref}`}</Text>
          <Text color="text-03">{t("recordState", { state: t(`states.${review.state}`), version: review.version })}</Text>
          <Section flexDirection="row" height="auto" justifyContent="start" wrap gap={2}>
            {review.state === "draft" && <Button disabled={busy} onClick={() => void decide(review, "submit")}>{t("submit")}</Button>}
            {review.state === "submitted" && <>
              <Button disabled={busy} onClick={() => void decide(review, "approve")}>{t("approve")}</Button>
              <Button disabled={busy} variant="danger" prominence="secondary" onClick={() => void decide(review, "reject")}>{t("reject")}</Button>
            </>}
            <Button prominence="secondary" onClick={() => setSelected(review.id)}>{t("audit")}</Button>
          </Section>
        </Section>)}
        {selected && <Section height="auto" alignItems="stretch" gap={2}>
          <Text font="heading-h3">{t("audit")}</Text>
          {audit?.map((event) => <Text key={event.version} font="secondary-mono" wordWrap="wrap-anywhere">{JSON.stringify(event)}</Text>)}
        </Section>}
      </Section>
    </SettingsLayouts.Body>
  </SettingsLayouts.Root>;
}
