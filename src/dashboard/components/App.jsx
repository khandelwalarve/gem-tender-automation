import React, { useState } from 'react';
import { useApi, postJson } from '../hooks/useApi';

/*
  Design direction: "Mission Control Ledger"
  — Procurement ops staff live in this screen all day; it needs to read like
    an instrument panel, not a marketing page. Dense, monospaced numerals,
    status expressed through a left-edge color bar (not badges/pills), and
    a strict three-column rhythm: queue → detail → trace.
  — Palette: near-black slate (#0B0E14) base, bone-white text (#E8E6DF),
    amber for human-attention items (#D98E3B), teal for healthy/auto (#3FA796),
    red-clay for rejected/error (#C75C4C). No blue — avoids the generic
    SaaS-dashboard-blue look.
  — Type: ui-monospace for all numeric/status data (bid IDs, scores, money),
    a plain system sans for prose/labels. The monospace is the signature:
    it makes the whole board feel like a terminal/ledger, fitting for an
    audit-driven government procurement tool.
*/

const STATUS_COLOR = {
  auto_submit: '#3FA796',
  human_approval: '#D98E3B',
  rejected: '#C75C4C',
  submitted: '#3FA796',
  pending: '#6B7280',
  failed: '#C75C4C',
  needs_human: '#D98E3B',
};

function StatusBar({ color }) {
  return <div style={{ width: 4, alignSelf: 'stretch', background: color || '#6B7280', borderRadius: 2 }} />;
}

function Money({ value }) {
  if (value == null) return <span style={{ opacity: 0.4 }}>—</span>;
  return <span style={{ fontFamily: 'ui-monospace, monospace' }}>₹{Number(value).toLocaleString('en-IN')}</span>;
}

function TenderRow({ tender, onSelect, selected }) {
  const color = STATUS_COLOR[tender.decision] || STATUS_COLOR[tender.status] || '#6B7280';
  return (
    <div
      onClick={() => onSelect(tender.id)}
      style={{
        display: 'flex',
        cursor: 'pointer',
        background: selected ? '#161B26' : 'transparent',
        borderBottom: '1px solid #1C212C',
        padding: '10px 14px',
        gap: 12,
        alignItems: 'center',
        transition: 'background 120ms ease',
      }}
    >
      <StatusBar color={color} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: 'ui-monospace, monospace', fontSize: 13, color: '#E8E6DF', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {tender.bid_id}
        </div>
        <div style={{ fontSize: 11, color: '#7A8094', marginTop: 2, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          {tender.decision || tender.status || 'pending'}
        </div>
      </div>
      {tender.deadline && (
        <div style={{ fontSize: 11, color: '#7A8094', fontFamily: 'ui-monospace, monospace' }}>
          {new Date(tender.deadline).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}
        </div>
      )}
    </div>
  );
}

function SummaryStrip() {
  const { data } = useApi('/stats/pipeline-summary');
  const s = data || {};
  const items = [
    { label: 'Tracked', value: s.total },
    { label: 'Auto-submit', value: s.auto_submit, color: STATUS_COLOR.auto_submit },
    { label: 'Needs review', value: s.human_approval, color: STATUS_COLOR.human_approval },
    { label: 'Rejected', value: s.rejected, color: STATUS_COLOR.rejected },
    { label: 'Submitted', value: s.submitted, color: STATUS_COLOR.submitted },
  ];
  return (
    <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid #1C212C' }}>
      {items.map((it, i) => (
        <div key={it.label} style={{ flex: 1, padding: '14px 18px', borderRight: i < items.length - 1 ? '1px solid #1C212C' : 'none' }}>
          <div style={{ fontSize: 22, fontFamily: 'ui-monospace, monospace', color: it.color || '#E8E6DF', fontWeight: 600 }}>
            {it.value ?? '—'}
          </div>
          <div style={{ fontSize: 11, color: '#7A8094', textTransform: 'uppercase', letterSpacing: '0.04em', marginTop: 2 }}>
            {it.label}
          </div>
        </div>
      ))}
    </div>
  );
}

function TraceEntry({ entry }) {
  const color = entry.event_type === 'error' ? STATUS_COLOR.rejected
    : entry.event_type === 'decision' ? STATUS_COLOR.human_approval
    : entry.event_type === 'warning' ? '#D98E3B'
    : '#3FA796';
  return (
    <div style={{ display: 'flex', gap: 10, padding: '8px 0', borderBottom: '1px solid #161B26' }}>
      <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, marginTop: 5, flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, color: '#E8E6DF' }}>
          <span style={{ color: '#7A8094', textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.04em', marginRight: 8 }}>{entry.phase?.replace(/_/g, ' ')}</span>
          {entry.step}
        </div>
        <div style={{ fontSize: 11, color: '#7A8094', fontFamily: 'ui-monospace, monospace', marginTop: 2 }}>
          {new Date(entry.occurred_at).toLocaleString('en-IN')}
        </div>
      </div>
    </div>
  );
}

function TenderDetail({ tenderId }) {
  const { data: tender } = useApi(tenderId ? `/tenders/${tenderId}` : null, { auto: !!tenderId });
  const { data: traceData } = useApi(tenderId ? `/tenders/${tenderId}/trace` : null, { auto: !!tenderId });

  if (!tenderId) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#4B5165', fontSize: 13 }}>
        Select a tender to view its trace
      </div>
    );
  }

  return (
    <div style={{ padding: 18, overflowY: 'auto', height: '100%' }}>
      {tender && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontFamily: 'ui-monospace, monospace', fontSize: 16, color: '#E8E6DF' }}>{tender.bid_id}</div>
          <div style={{ display: 'flex', gap: 18, marginTop: 8, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 10, color: '#7A8094', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Decision</div>
              <div style={{ fontSize: 13, color: STATUS_COLOR[tender.decision] || '#E8E6DF', marginTop: 2 }}>{tender.decision || 'pending'}</div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: '#7A8094', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Submission</div>
              <div style={{ fontSize: 13, color: '#E8E6DF', marginTop: 2 }}>{tender.submission_status || '—'}</div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: '#7A8094', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Deadline</div>
              <div style={{ fontSize: 13, color: '#E8E6DF', marginTop: 2, fontFamily: 'ui-monospace, monospace' }}>
                {tender.deadline ? new Date(tender.deadline).toLocaleString('en-IN') : '—'}
              </div>
            </div>
          </div>
        </div>
      )}

      <div style={{ fontSize: 11, color: '#7A8094', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 10 }}>
        Process trace
      </div>
      <div>
        {(traceData?.trace || []).map((e) => (
          <TraceEntry key={e.id} entry={e} />
        ))}
        {traceData && traceData.trace.length === 0 && (
          <div style={{ fontSize: 12, color: '#4B5165', padding: '20px 0' }}>No events logged yet.</div>
        )}
      </div>
    </div>
  );
}

function PendingReviewCard({ review, onDecided }) {
  const [busy, setBusy] = useState(false);

  async function decide(decision) {
    setBusy(true);
    try {
      await postJson(`/reviews/${review.id}/decide?tender_id=${review.tender_id}`, { decision });
      onDecided();
    } finally {
      setBusy(false);
    }
  }

  const hoursLeft = review.deadline ? (new Date(review.deadline) - new Date()) / 36e5 : null;

  return (
    <div style={{ border: '1px solid #1C212C', borderRadius: 6, padding: 12, marginBottom: 10, background: '#10141D' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div style={{ fontFamily: 'ui-monospace, monospace', fontSize: 13, color: '#E8E6DF' }}>{review.bid_id}</div>
        {hoursLeft != null && (
          <div style={{ fontSize: 11, color: hoursLeft < 6 ? STATUS_COLOR.rejected : '#7A8094', fontFamily: 'ui-monospace, monospace' }}>
            {hoursLeft > 0 ? `${hoursLeft.toFixed(1)}h left` : 'overdue'}
          </div>
        )}
      </div>
      <div style={{ fontSize: 11, color: '#7A8094', marginTop: 4 }}>Assigned: {review.assigned_to}</div>
      <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
        <button
          disabled={busy}
          onClick={() => decide('approved')}
          style={{ flex: 1, background: STATUS_COLOR.auto_submit, border: 'none', borderRadius: 4, padding: '6px 0', fontSize: 11, color: '#0B0E14', fontWeight: 600, cursor: 'pointer' }}
        >
          Approve
        </button>
        <button
          disabled={busy}
          onClick={() => decide('rejected')}
          style={{ flex: 1, background: 'transparent', border: '1px solid #C75C4C', borderRadius: 4, padding: '6px 0', fontSize: 11, color: '#C75C4C', fontWeight: 600, cursor: 'pointer' }}
        >
          Reject
        </button>
      </div>
    </div>
  );
}

export default function App() {
  const [selectedTenderId, setSelectedTenderId] = useState(null);
  const { data: tendersData, refetch: refetchTenders } = useApi('/tenders', { params: { limit: 100 } });
  const { data: reviewsData, refetch: refetchReviews } = useApi('/pending-reviews');

  return (
    <div style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', background: '#0B0E14', color: '#E8E6DF', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '14px 18px', borderBottom: '1px solid #1C212C', display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <span style={{ fontFamily: 'ui-monospace, monospace', fontSize: 15, fontWeight: 600 }}>GeM Tender Automation</span>
        <span style={{ fontSize: 11, color: '#4B5165' }}>PS ITCONS</span>
      </div>

      <SummaryStrip />

      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <div style={{ width: 280, borderRight: '1px solid #1C212C', overflowY: 'auto' }}>
          {(tendersData?.items || []).map((t) => (
            <TenderRow key={t.id} tender={t} selected={t.id === selectedTenderId} onSelect={setSelectedTenderId} />
          ))}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <TenderDetail tenderId={selectedTenderId} />
        </div>

        <div style={{ width: 300, borderLeft: '1px solid #1C212C', padding: 14, overflowY: 'auto' }}>
          <div style={{ fontSize: 11, color: '#7A8094', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 12 }}>
            Awaiting your decision
          </div>
          {(reviewsData?.items || []).map((r) => (
            <PendingReviewCard
              key={r.id}
              review={r}
              onDecided={() => {
                refetchReviews();
                refetchTenders();
              }}
            />
          ))}
          {reviewsData && reviewsData.items.length === 0 && (
            <div style={{ fontSize: 12, color: '#4B5165' }}>Nothing pending. Queue is clear.</div>
          )}
        </div>
      </div>
    </div>
  );
}
