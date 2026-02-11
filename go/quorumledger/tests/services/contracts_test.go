package services_test

import (
	"testing"

	"quorumledger/shared/contracts"
)

func TestContractsFields(t *testing.T) {
	if len(contracts.RequiredEventFields) < 6 {
		t.Fatalf("expected richer event contract")
	}
	if len(contracts.RequiredCommandFields) < 6 {
		t.Fatalf("expected richer command contract")
	}
}

func TestServiceSLOContracts(t *testing.T) {
	for _, service := range []string{"gateway", "consensus", "security"} {
		entry, ok := contracts.ServiceSLO[service]
		if !ok {
			t.Fatalf("missing SLO for %s", service)
		}
		if entry["availability"] < 0.997 {
			t.Fatalf("availability too low for %s", service)
		}
	}
}
