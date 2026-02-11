# Slack Thread: Real-time Collaboration and Search Sync Issues

**Channel:** #eng-helixops-support
**Date:** November 21, 2024
**Participants:** @alex.kumar, @priya.sharma, @tom.wilson, @lisa.chen, @dev-oncall

---

**@alex.kumar** 10:23 AM
Hey team, we're getting reports from the collab team that users are experiencing weird issues with real-time document editing. New users joining a session don't see the latest edits - they have to refresh to get the current state. Anyone seen this before?

---

**@priya.sharma** 10:25 AM
Yeah I noticed something similar yesterday. When I joined a doc that @tom.wilson was editing, I didn't see his last few changes until I manually refreshed. Thought it was just my network.

---

**@tom.wilson** 10:28 AM
Wait really? I was editing that doc for like 10 minutes before you joined. You should have seen everything... Let me check the CollabService logs.

---

**@tom.wilson** 10:34 AM
Found something interesting. The `editFlow` is using `MutableSharedFlow(replay = 0)`. That means new subscribers don't get any buffered emissions - they only see events emitted AFTER they subscribe.

```kotlin
private val editFlow = MutableSharedFlow<CollabEdit>(replay = 0)
```

So if someone joins after the last edit was emitted, they miss it entirely. Should probably be `replay = 1` at minimum.

---

**@alex.kumar** 10:37 AM
That would explain it. But there's another issue - sometimes when two people merge their changes, the version numbers come out inconsistent. Like if I have version (2,3) and you have (1,4), merging gives different results depending on who initiates.

---

**@priya.sharma** 10:41 AM
Oh no, is the plus operator not commutative?

Let me check... yeah the `DocumentVersion.plus()` looks sus:

```kotlin
operator fun plus(other: DocumentVersion): DocumentVersion {
    return DocumentVersion(
        major = this.major + other.minor,  // asymmetric!
        minor = this.minor + other.major
    )
}
```

So `a + b != b + a`. That's definitely going to cause merge conflicts.

---

**@lisa.chen** 10:45 AM
Jumping in - I'm debugging a related issue in the search module. Users are reporting that sometimes search results are just wrong or missing. And the performance is terrible - cache seems completely ineffective.

Running the search tests and seeing these failures:
```
SearchTests > testSealedClassDiscriminator FAILED
SearchTests > testCacheKeyStability FAILED
SearchTests > testCacheStampede FAILED
SearchTests > testSqlOperatorPrecedence FAILED
```

---

**@tom.wilson** 10:48 AM
What's the sealed class discriminator issue?

---

**@lisa.chen** 10:52 AM
Two subclasses of `SearchResult` have the same `@SerialName("document")`:

```kotlin
@SerialName("document")
data class DocumentResult(...) : SearchResult()

@SerialName("document")  // COLLISION!
data class GraphNodeResult(...) : SearchResult()
```

When we try to deserialize a GraphNodeResult, it gets parsed as DocumentResult and fails. Classic polymorphic serialization bug.

---

**@alex.kumar** 10:55 AM
What about the cache issues?

---

**@lisa.chen** 10:58 AM
Two problems:

1. Cache key uses `query.toString()` on a data class. If filters are in different order but logically equivalent, you get different cache keys. Cache miss every time.

2. No lock around cache population. Under load, 100 concurrent requests all hit miss simultaneously, all execute the expensive query, then all write to cache. Classic stampede.

Also found the SQL precedence thing:
```kotlin
SearchIndex.content like "%$query%" or
    (SearchIndex.documentId eq ownerId) and
    (SearchIndex.score greater 0.5)
```

Without explicit parentheses, operator precedence makes this evaluate wrong. The AND binds tighter than OR.

---

**@priya.sharma** 11:02 AM
Related collab issue - WebSocket sessions aren't closing cleanly. Looking at the error handling:

```kotlin
} finally {
    sessions[documentId]?.remove(session)
    // No session.close() call!
}
```

We remove the session from our tracking but never send a proper close frame to the client. Clients don't know if we intentionally closed or if it's a network error.

---

**@tom.wilson** 11:05 AM
And look at this - the `operationalTransform` engine uses `lazy(LazyThreadSafetyMode.NONE)` but it's accessed from multiple coroutines. If two coroutines hit it during initialization, we get a race condition.

---

**@dev-oncall** 11:10 AM
Just got paged about analytics logs being messed up. Users report that trace IDs and user context are missing from log entries when processing events async.

---

**@lisa.chen** 11:13 AM
That's probably MDC context not propagating to coroutines. MDC is ThreadLocal-based, but when you `withContext(Dispatchers.IO)`, you might resume on a different thread. Need to use `MDCContext()` to carry it across.

---

**@alex.kumar** 11:15 AM
OK so to summarize the issues we need to track:

**Collab Module:**
- [ ] SharedFlow replay buffer missing - new subscribers miss state
- [ ] DocumentVersion plus operator not commutative
- [ ] Lazy init race condition in OT engine
- [ ] WebSocket close frames not sent

**Search Module:**
- [ ] Sealed class serialName collision
- [ ] Cache key stability (toString not suitable)
- [ ] Cache stampede (no locking)
- [ ] SQL operator precedence

**Analytics:**
- [ ] MDC context lost across coroutine dispatchers

Tests to check:
```bash
./gradlew :collab:test
./gradlew :search:test
./gradlew :analytics:test
```

---

**@priya.sharma** 11:18 AM
I'll take collab. @lisa.chen you good with search?

---

**@lisa.chen** 11:19 AM
On it. Might need to look at the DSL marker issue too - there's a `@SearchDsl` annotation defined but not applied correctly, so nested DSL scopes are leaking.

---

**@tom.wilson** 11:22 AM
Found another search issue - the `formatResult` function has a non-exhaustive when:

```kotlin
return when (result) {
    is SearchResult.DocumentResult -> ...
    else -> throw IllegalStateException("Unknown result type")
}
```

GraphNodeResult falls through to the else and crashes. Should handle all sealed subclasses.

---

**@dev-oncall** 11:25 AM
Tickets created:
- HELIX-4821: Collab SharedFlow and version merging
- HELIX-4822: Search serialization and caching
- HELIX-4823: Analytics MDC propagation

Let's sync at 2pm to review progress.

---

**@alex.kumar** 11:27 AM
Sounds good. Also just noticed the graph module has similar issues - same Mutex for reads and writes, cache keys missing schema version, and some JSON parsing that doesn't handle unknown fields. Might want to add HELIX-4824 for graph.

---

**@lisa.chen** 11:30 AM
:eyes: the whole platform needs a Kotlin idioms review. These are all classic Kotlin/coroutines gotchas.
