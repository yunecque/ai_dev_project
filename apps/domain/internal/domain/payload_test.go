package domain

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestOutboxPayloadMatchesEventContract(t *testing.T) {
	event := Event{
		EventID:    "11111111-1111-1111-1111-111111111111",
		EventType:  eventTypeRequestCreated,
		OccurredAt: "2026-09-22T00:00:00Z",
		Request:    Request{ID: "22222222-2222-2222-2222-222222222222", Title: "t", Status: statusCreated, CreatedAt: "2026-09-22T00:00:00Z"},
	}
	payload, err := json.Marshal(outboxPayload{
		EventID:    event.EventID,
		EventType:  event.EventType,
		OccurredAt: event.OccurredAt,
		Request:    requestRecord{ID: event.Request.ID, Title: event.Request.Title, Status: event.Request.Status, CreatedAt: event.Request.CreatedAt},
	})
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var decoded map[string]json.RawMessage
	if err := json.Unmarshal(payload, &decoded); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	schemaPath := filepath.Join("..", "..", "..", "..", "contracts", "events", "request-created.schema.json")
	raw, err := os.ReadFile(schemaPath)
	if err != nil {
		t.Fatalf("read event schema: %v", err)
	}
	var schema struct {
		Required   []string `json:"required"`
		Properties map[string]struct {
			Properties map[string]any `json:"properties"`
		} `json:"properties"`
	}
	if err := json.Unmarshal(raw, &schema); err != nil {
		t.Fatalf("parse event schema: %v", err)
	}

	for _, key := range schema.Required {
		if _, ok := decoded[key]; !ok {
			t.Fatalf("payload missing required field %q", key)
		}
	}

	var request map[string]json.RawMessage
	if err := json.Unmarshal(decoded["request"], &request); err != nil {
		t.Fatalf("unmarshal request: %v", err)
	}
	for key := range schema.Properties["request"].Properties {
		if _, ok := request[key]; !ok {
			t.Fatalf("request payload missing field %q", key)
		}
	}

	if string(decoded["event_type"]) != `"`+eventTypeRequestCreated+`"` {
		t.Fatalf("event_type = %s", decoded["event_type"])
	}
}

func TestStatusChangedPayloadMatchesEventContract(t *testing.T) {
	event := Event{
		EventID:        "11111111-1111-1111-1111-111111111111",
		EventType:      eventTypeRequestStatusChanged,
		OccurredAt:     "2026-09-22T00:00:00Z",
		PreviousStatus: statusCreated,
		Request:        Request{ID: "22222222-2222-2222-2222-222222222222", Status: statusTriaged},
	}
	payload, err := buildPayload(event)
	if err != nil {
		t.Fatalf("buildPayload: %v", err)
	}

	var decoded map[string]json.RawMessage
	if err := json.Unmarshal(payload, &decoded); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	schemaPath := filepath.Join("..", "..", "..", "..", "contracts", "events", "request-status-changed.schema.json")
	raw, err := os.ReadFile(schemaPath)
	if err != nil {
		t.Fatalf("read event schema: %v", err)
	}
	var schema struct {
		Required   []string `json:"required"`
		Properties map[string]struct {
			Properties map[string]any `json:"properties"`
		} `json:"properties"`
	}
	if err := json.Unmarshal(raw, &schema); err != nil {
		t.Fatalf("parse event schema: %v", err)
	}

	for _, key := range schema.Required {
		if _, ok := decoded[key]; !ok {
			t.Fatalf("payload missing required field %q", key)
		}
	}

	var request map[string]json.RawMessage
	if err := json.Unmarshal(decoded["request"], &request); err != nil {
		t.Fatalf("unmarshal request: %v", err)
	}
	for key := range schema.Properties["request"].Properties {
		if _, ok := request[key]; !ok {
			t.Fatalf("request payload missing field %q", key)
		}
	}

	if string(decoded["event_type"]) != `"`+eventTypeRequestStatusChanged+`"` {
		t.Fatalf("event_type = %s", decoded["event_type"])
	}
	if string(request["previous_status"]) != `"`+statusCreated+`"` {
		t.Fatalf("previous_status = %s", request["previous_status"])
	}
}
