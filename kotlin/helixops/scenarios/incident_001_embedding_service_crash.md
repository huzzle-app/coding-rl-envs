# INC-2024-0847: Embedding Service Crashes on Document Processing

**Severity:** P1 - Critical
**Status:** Open
**Reported:** 2024-11-15 03:42 UTC
**Affected Service:** embeddings
**On-Call Engineer:** @sarah.chen

---

## Summary

The document embedding pipeline is experiencing intermittent crashes during batch processing operations. The service terminates abruptly with `UninitializedPropertyAccessException` when processing documents for semantic search indexing. Additionally, customers report that batch embedding jobs are failing silently, leaving partial results in the vector store.

## Business Impact

- **450+ documents** stuck in "processing" state for >4 hours
- MindVault Enterprise customers cannot use semantic search functionality
- SLA breach imminent: embeddings must complete within 2 hours per contract
- **Revenue at risk:** $180K/month Enterprise tier includes semantic search

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 03:42 | PagerDuty alert: EmbeddingService health check failed |
| 03:45 | Service auto-restarted by Kubernetes, immediately crashed again |
| 03:51 | Manual investigation started |
| 04:12 | Identified crash pattern in logs, but root cause unclear |
| 04:30 | Escalated to engineering team |

## Symptoms

1. **Startup Crashes**: Service sometimes crashes immediately on first embedding request
2. **Batch Processing Failures**: When processing multiple documents concurrently, if one fails, all others are abandoned
3. **Deep Document Trees**: Documents with deeply nested sections (legal contracts, technical manuals) cause stack overflow

## Logs

```
2024-11-15T03:42:17.234Z ERROR [embeddings] --- UninitializedPropertyAccessException:
    lateinit property modelEndpoint has not been initialized
    at com.mindvault.embeddings.EmbeddingService.compute(EmbeddingService.kt:91)
    at com.mindvault.embeddings.EmbeddingService$computeBatchEmbeddings$2.invokeSuspend(EmbeddingService.kt:36)

2024-11-15T03:43:55.892Z ERROR [embeddings] --- CancellationException during batch processing
    Job was cancelled; 3 of 12 embeddings completed before failure
    Partial results not cleaned up from vector store
    at kotlinx.coroutines.JobSupportKt.awaitAll(JobSupport.kt:478)

2024-11-15T04:01:33.445Z ERROR [embeddings] --- StackOverflowError
    Processing document: DOC-2024-91823 (Legal Agreement v47)
    Document tree depth: 1247 levels
    at com.mindvault.embeddings.EmbeddingService.embedDocumentTree(EmbeddingService.kt:63)
    at com.mindvault.embeddings.EmbeddingService.embedDocumentTree(EmbeddingService.kt:63)
    [... 1000+ repeated frames ...]
```

## Reproduction Steps

The QA team confirmed the following test failures in the embeddings module:

```
./gradlew :embeddings:test

EmbeddingTests > testLateinitPropertyInitialization FAILED
EmbeddingTests > testBatchEmbeddingCancellation FAILED
EmbeddingTests > testDeepDocumentTreeEmbedding FAILED
EmbeddingTests > testBatchEmbeddingPartialFailure FAILED
```

## Investigation Notes

1. The `EmbeddingService` appears to have configuration properties that may not always be initialized before use
2. When using `async`/`awaitAll` for batch processing, cancellation of one coroutine seems to affect all siblings without proper cleanup
3. The document tree embedding uses recursion without any depth limits
4. The external AI API returns JSON in a different format than the parser expects

## Related Alerts

- `embedding_latency_p99 > 30s` (last 2 hours)
- `vector_store_orphaned_embeddings` count increasing
- `embedding_batch_success_rate < 50%`

## Action Items

- [ ] Investigate why configuration properties aren't initialized before service calls
- [ ] Review coroutine cancellation handling in batch operations
- [ ] Add safeguards for deeply nested document structures
- [ ] Verify JSON response parsing from the embedding API

---

**Note:** Do not restart the service again until root cause is identified. Each restart creates more orphaned partial embeddings in the vector store.
