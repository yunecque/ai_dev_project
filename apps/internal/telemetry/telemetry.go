// Package telemetry wires OpenTelemetry traces and metrics for the platform services.
//
// Export is opt-in via OTEL_EXPORTER_OTLP_ENDPOINT; without it providers are installed but
// export nothing, so local runs need no collector. Redaction of secrets/tokens/PII happens in
// the OTel Collector before export (ADR-0010); services are responsible for never attaching
// sensitive values as attributes in the first place.
package telemetry

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"os"

	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"google.golang.org/grpc"
)

const serviceNameKey = "service.name"

// Setup installs the global tracer/meter providers and W3C trace propagation, returning a
// shutdown function. When OTEL_EXPORTER_OTLP_ENDPOINT is unset, no data is exported.
func Setup(ctx context.Context, serviceName string) (func(context.Context) error, error) {
	res := resource.NewWithAttributes("", attribute.String(serviceNameKey, serviceName))

	traceOpts := []sdktrace.TracerProviderOption{sdktrace.WithResource(res)}
	metricOpts := []metric.Option{metric.WithResource(res)}

	if endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT"); endpoint != "" {
		traceExporter, err := otlptracegrpc.New(ctx)
		if err != nil {
			return nil, fmt.Errorf("telemetry: trace exporter: %w", err)
		}
		traceOpts = append(traceOpts, sdktrace.WithBatcher(traceExporter))

		metricExporter, err := otlpmetricgrpc.New(ctx)
		if err != nil {
			return nil, fmt.Errorf("telemetry: metric exporter: %w", err)
		}
		metricOpts = append(metricOpts, metric.WithReader(metric.NewPeriodicReader(metricExporter)))
	}

	tracerProvider := sdktrace.NewTracerProvider(traceOpts...)
	meterProvider := metric.NewMeterProvider(metricOpts...)

	otel.SetTracerProvider(tracerProvider)
	otel.SetMeterProvider(meterProvider)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{}, propagation.Baggage{},
	))

	shutdown := func(ctx context.Context) error {
		return errors.Join(tracerProvider.Shutdown(ctx), meterProvider.Shutdown(ctx))
	}
	return shutdown, nil
}

// HTTPHandler instruments an HTTP handler with a server span and HTTP metrics.
func HTTPHandler(handler http.Handler, operation string) http.Handler {
	return otelhttp.NewHandler(handler, operation)
}

// GRPCServerOption enables server-side span creation and trace extraction.
func GRPCServerOption() grpc.ServerOption {
	return grpc.StatsHandler(otelgrpc.NewServerHandler())
}

// GRPCClientOption enables client-side span creation and trace injection into metadata.
func GRPCClientOption() grpc.DialOption {
	return grpc.WithStatsHandler(otelgrpc.NewClientHandler())
}
