"use client";

import { useState } from "react";
import useSWR from "swr";
import { useTranslations } from "next-intl";
import { array, boolean, mixed, number, object, string, type InferType } from "yup";
import { Button, InputTextArea, Text } from "@opal/components";
import { Section, SettingsLayouts } from "@opal/layouts";

const reviewSchema = object({
  id: string().required(), owner_id: string().required(), payload_hash: string().required(),
  state: mixed<"draft" | "submitted" | "approved" | "rejected">().oneOf(["draft", "submitted", "approved", "rejected"]).required(), version: number().required(),
  payload: object({
    vendor_ref: string().required(), tender_ref: string().required(),
    requirements: array().of(object({ key: string().required(), label: string().required(), mandatory: boolean().required() }).required()).required(),
    evidence: array().of(object({ requirement_key: string().required(), document_ref: string().required(), version: string().required(), quote: string().required(), valid_until: string().nullable().optional() }).required()).required(),
  }).required(),
}).required();
type Review = InferType<typeof reviewSchema>;
const reviewsSchema = array().of(reviewSchema).required();
const auditSchema = array().of(object({ actor_id: string().required(), action: string().required(), version: number().required(), payload_hash: string().required(), note: string().defined() }).required()).required();
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
  return reviewsSchema.validateSync(await (await request(url)).json(), { strict: true });
}

async function fetchAudit(url: string): Promise<InferType<typeof auditSchema>> {
  return auditSchema.validateSync(await (await request(url)).json(), { strict: true });
}

export default function ProcurementPage() {
  const t = useTranslations("procurement");
  const [raw, setRaw] = useState(JSON.stringify(sample, null, 2));
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const [details, setDetails] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const { data, error: loadError, isLoading, mutate } = useSWR("/api/admin/procurement", fetchReviews);
  const { data: audit, mutate: refreshAudit } = useSWR(selected ? `/api/admin/procurement/${selected}/audit` : null, fetchAudit);

  async function create(): Promise<void> {
    setBusy(true); setError("");
    try {
      const payload: unknown = JSON.parse(raw);
      await request("/api/admin/procurement", { method: "POST", headers: { "Idempotency-Key": requestKey }, body: JSON.stringify(payload) });
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
        <InputTextArea aria-label={t("newCase")} mono rows={12} maxLength={200000} value={raw} onChange={(event) => { setRaw(event.target.value); setRequestKey(crypto.randomUUID()); }} />
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
            <Button prominence="secondary" onClick={() => setDetails(details === review.id ? null : review.id)}>{t("evidencePackage")}</Button>
            {review.state === "draft" && <Button disabled={busy} onClick={() => void decide(review, "submit")}>{t("submit")}</Button>}
            {review.state === "submitted" && <>
              <Button disabled={busy} onClick={() => void decide(review, "approve")}>{t("approve")}</Button>
              <Button disabled={busy} variant="danger" prominence="secondary" onClick={() => void decide(review, "reject")}>{t("reject")}</Button>
            </>}
            <Button prominence="secondary" onClick={() => setSelected(review.id)}>{t("audit")}</Button>
          </Section>
          {details === review.id && <Section height="auto" alignItems="stretch" gap={3}>
            <Text font="secondary-mono" wordWrap="wrap-anywhere">{review.payload_hash}</Text>
            {review.payload.requirements.map((requirement) => <Section key={requirement.key} height="auto" alignItems="stretch" gap={2}>
              <Text font="main-content-emphasis">{`${requirement.label} · ${t(requirement.mandatory ? "mandatory" : "optional")}`}</Text>
              {review.payload.evidence.filter((evidence) => evidence.requirement_key === requirement.key).map((evidence, index) => <Section key={`${evidence.document_ref}-${index}`} height="auto" alignItems="stretch" gap={1}>
                <Text color="text-03" wordWrap="wrap-anywhere">{`${evidence.document_ref} / ${evidence.version}`}</Text>
                <Text wordWrap="wrap-anywhere">{evidence.quote}</Text>
                {evidence.valid_until && <Text color="text-03">{t("validUntil", { date: evidence.valid_until })}</Text>}
              </Section>)}
              {!review.payload.evidence.some((evidence) => evidence.requirement_key === requirement.key) && <Text color="status-error-05">{t("missingEvidence")}</Text>}
            </Section>)}
          </Section>}
        </Section>)}
        {selected && <Section height="auto" alignItems="stretch" gap={2}>
          <Text font="heading-h3">{t("audit")}</Text>
          {audit?.map((event) => <Text key={event.version} font="secondary-mono" wordWrap="wrap-anywhere">{JSON.stringify(event)}</Text>)}
        </Section>}
      </Section>
    </SettingsLayouts.Body>
  </SettingsLayouts.Root>;
}
