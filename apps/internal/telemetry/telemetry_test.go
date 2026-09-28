package telemetry

import (
	"context"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/sdk/trace/tracetest"
	"go.opentelemetry.io/otel/trace"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/test/bufconn"
	"google.golang.org/protobuf/types/known/emptypb"
)

func installTestProvider(t *testing.T) (*tracetest.InMemoryExporter, func()) {
	t.Helper()
	exporter := tracetest.NewInMemoryExporter()
	provider := sdktrace.NewTracerProvider(
		sdktrace.WithSpanProcessor(sdktrace.NewSimpleSpanProcessor(exporter)),
	)
	previous := otel.GetTracerProvider()
	otel.SetTracerProvider(provider)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{}, propagation.Baggage{},
	))
	return exporter, func() {
		_ = provider.Shutdown(context.Background())
		otel.SetTracerProvider(previous)
	}
}

func TestSetupWithoutEndpoint(t *testing.T) {
	t.Setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
	shutdown, err := Setup(context.Background(), "test-service")
	if err != nil {
		t.Fatalf("Setup: %v", err)
	}
	if err := shutdown(context.Background()); err != nil {
		t.Fatalf("shutdown: %v", err)
	}
}

func TestHTTPHandlerEmitsSpan(t *testing.T) {
	exporter, cleanup := installTestProvider(t)
	defer cleanup()

	handler := HTTPHandler(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	}), "test.http")
	server := httptest.NewServer(handler)
	defer server.Close()

	response, err := http.Get(server.URL)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	_ = response.Body.Close()

	for _, span := range exporter.GetSpans() {
		if span.SpanKind == trace.SpanKindServer {
			return
		}
	}
	t.Fatalf("server span not exported: %+v", exporter.GetSpans())
}

type echoService interface {
	Echo(ctx context.Context, in *emptypb.Empty) (*emptypb.Empty, error)
}

type echoServer struct {
	traceID chan string
}

func (s *echoServer) Echo(ctx context.Context, _ *emptypb.Empty) (*emptypb.Empty, error) {
	spanContext := trace.SpanContextFromContext(ctx)
	s.traceID <- spanContext.TraceID().String()
	return &emptypb.Empty{}, nil
}

func echoServiceDesc() *grpc.ServiceDesc {
	return &grpc.ServiceDesc{
		ServiceName: "test.Echo",
		HandlerType: (*echoService)(nil),
		Methods: []grpc.MethodDesc{
			{
				MethodName: "Echo",
				Handler: func(srv any, ctx context.Context, dec func(any) error, interceptor grpc.UnaryServerInterceptor) (any, error) {
					in := new(emptypb.Empty)
					if err := dec(in); err != nil {
						return nil, err
					}
					if interceptor == nil {
						return srv.(echoService).Echo(ctx, in)
					}
					info := &grpc.UnaryServerInfo{Server: srv, FullMethod: "/test.Echo/Echo"}
					handler := func(ctx context.Context, req any) (any, error) {
						return srv.(echoService).Echo(ctx, req.(*emptypb.Empty))
					}
					return interceptor(ctx, in, info, handler)
				},
			},
		},
	}
}

func TestGRPCTracePropagation(t *testing.T) {
	installTestProvider(t)

	listener := bufconn.Listen(1024 * 1024)
	impl := &echoServer{traceID: make(chan string, 1)}

	server := grpc.NewServer(GRPCServerOption())
	server.RegisterService(echoServiceDesc(), impl)
	go func() { _ = server.Serve(listener) }()
	defer server.Stop()

	conn, err := grpc.NewClient("passthrough:///bufnet",
		grpc.WithContextDialer(func(context.Context, string) (net.Conn, error) { return listener.Dial() }),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		GRPCClientOption(),
	)
	if err != nil {
		t.Fatalf("dial: %v", err)
	}
	defer func() { _ = conn.Close() }()

	ctx, span := otel.Tracer("test").Start(context.Background(), "client")
	if err := conn.Invoke(ctx, "/test.Echo/Echo", &emptypb.Empty{}, &emptypb.Empty{}); err != nil {
		t.Fatalf("invoke: %v", err)
	}
	span.End()

	select {
	case serverTraceID := <-impl.traceID:
		if serverTraceID != span.SpanContext().TraceID().String() {
			t.Fatalf("trace id mismatch: server=%s client=%s", serverTraceID, span.SpanContext().TraceID())
		}
	case <-time.After(2 * time.Second):
		t.Fatal("server did not observe a trace context")
	}
}

// TestGoldenPathObservabilitySmoke traces one request across an instrumented HTTP handler that
// calls an instrumented gRPC backend: it must produce a single trace with server spans on both
// hops, and it must not record the Authorization header value as a span attribute.
func TestGoldenPathObservabilitySmoke(t *testing.T) {
	exporter, cleanup := installTestProvider(t)
	defer cleanup()

	listener := bufconn.Listen(1024 * 1024)
	impl := &echoServer{traceID: make(chan string, 1)}

	grpcServer := grpc.NewServer(GRPCServerOption())
	grpcServer.RegisterService(echoServiceDesc(), impl)
	go func() { _ = grpcServer.Serve(listener) }()
	defer grpcServer.Stop()

	conn, err := grpc.NewClient("passthrough:///bufnet",
		grpc.WithContextDialer(func(context.Context, string) (net.Conn, error) { return listener.Dial() }),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		GRPCClientOption(),
	)
	if err != nil {
		t.Fatalf("dial: %v", err)
	}
	defer func() { _ = conn.Close() }()

	handler := HTTPHandler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := conn.Invoke(r.Context(), "/test.Echo/Echo", &emptypb.Empty{}, &emptypb.Empty{}); err != nil {
			http.Error(w, "backend", http.StatusBadGateway)
			return
		}
		w.WriteHeader(http.StatusOK)
	}), "golden-path")
	httpServer := httptest.NewServer(handler)
	defer httpServer.Close()

	request, err := http.NewRequestWithContext(context.Background(), http.MethodPost, httpServer.URL+"/requests", nil)
	if err != nil {
		t.Fatalf("request: %v", err)
	}
	request.Header.Set("Authorization", "Bearer super-secret-token")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatalf("do: %v", err)
	}
	_ = response.Body.Close()

	traceIDs := map[trace.TraceID]int{}
	serverSpans, clientSpans := 0, 0
	for _, span := range exporter.GetSpans() {
		if !span.SpanContext.IsValid() {
			continue
		}
		traceIDs[span.SpanContext.TraceID()]++
		switch span.SpanKind {
		case trace.SpanKindServer:
			serverSpans++
		case trace.SpanKindClient:
			clientSpans++
		}
		for _, attribute := range span.Attributes {
			if strings.Contains(attribute.Value.AsString(), "super-secret-token") {
				t.Fatalf("sensitive value leaked into span %q attribute %s", span.Name, attribute.Key)
			}
		}
	}

	if len(traceIDs) != 1 {
		t.Fatalf("expected a single trace, got %d", len(traceIDs))
	}
	if serverSpans < 2 {
		t.Fatalf("expected server spans on both hops, got %d", serverSpans)
	}
	if clientSpans < 1 {
		t.Fatalf("expected a gRPC client span, got %d", clientSpans)
	}
}
