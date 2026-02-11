# Slack Discussion: Search and Indexing Problems

## #backend-eng - January 24, 2024

---

**@support.lisa** (08:30):
> Hey team, getting a lot of tickets about search. Multiple customers saying they can't find documents they know exist. Also some complaints about autocomplete being "stuck" showing old suggestions. Anyone know what's going on?

**@dev.marcus** (08:42):
> Let me check the indexing pipeline. What kind of documents are they unable to find?

**@support.lisa** (08:45):
> Tickets say:
> - "Created document yesterday, search can't find it"
> - "Renamed document 2 days ago, old name still shows up, new name doesn't"
> - "Deleted document shows in search results"

**@sre.kim** (08:52):
> Looking at our indexing metrics:
> ```
> documents_created_24h: 12,456
> documents_indexed_24h: 11,892
> indexing_gap: 564 documents (4.5% loss)
> ```
> We're losing documents during indexing.

---

**@dev.marcus** (09:05):
> Found a problem in the indexing pipeline. Look at this:
> ```javascript
> async indexDocument(doc) {
>   // We consume the message from queue BEFORE indexing completes
>   try {
>     await this._indexToElasticsearch(doc);
>   } catch (error) {
>     // Error swallowed - message already acknowledged!
>     console.error('Indexing failed:', error);
>   }
> }
> ```
> If Elasticsearch is slow or throws an error, we lose the document. It's acked from the queue but never indexed.

**@sre.kim** (09:12):
> That explains the gap. ES was having issues yesterday afternoon:
> ```
> 14:00-14:30 UTC: Elasticsearch cluster yellow
> 14:15-14:25 UTC: 234 indexing timeouts
> ```
> All those documents are gone from the indexing queue now.

---

**@dev.sarah** (09:25):
> Found another issue. The autocomplete cache problem:
> ```javascript
> async autocomplete(prefix) {
>   // Cache never expires!
>   if (this.autocompleteCache.has(prefix)) {
>     return this.autocompleteCache.get(prefix);
>   }
>   // ... compute and cache ...
> }
> ```
> Once a prefix is cached, it's cached forever. Even if documents are renamed/deleted, autocomplete shows stale data.

**@support.lisa** (09:30):
> That matches the complaints. One customer renamed "Q3 Report" to "Q3 Financial Summary" but autocomplete still suggests "Q3 Report".

---

**@dev.alex** (09:45):
> I'm looking at a performance issue. Customer ticket says search is timing out:
> ```
> POST /api/v1/search
> {"q": "project status update meeting notes"}
>
> Response: 504 Gateway Timeout (30s)
> ```

**@dev.alex** (09:48):
> Found it. Multi-word searches cause exponential slowdown:
> ```javascript
> calculateRelevanceScore(termFrequency, documentFrequency, documentLength) {
>   const tf = Math.log(1 + termFrequency);
>   const idf = Math.log(1 / (1 + documentFrequency));
>   const lengthNorm = 1 / Math.sqrt(documentLength);
>   return tf * idf * lengthNorm;
> }
> ```
> The IDF calculation is wrong - it should be `log(totalDocs / (1 + documentFrequency))`. Current formula gives negative scores for common terms, causing sorting issues and extra computation.

---

**@sre.kim** (10:05):
> More bad news. Just got an alert from security scanner:
> ```
> CRITICAL: SQL injection vulnerability detected
> Endpoint: GET /api/v1/search
> Payload: q=test' OR 1=1--
> Response: Error indicates SQL parsing
> ```

**@dev.marcus** (10:12):
> Oh no. Looking at the code:
> ```javascript
> const query = `SELECT * FROM documents WHERE content LIKE '%${q}%' ORDER BY ${sort || 'created_at'}`;
> ```
> That's... that's string interpolation. Not parameterized.

**@dev.sarah** (10:15):
> Same with the Elasticsearch query:
> ```javascript
> const esQuery = {
>   query: {
>     query_string: {
>       query: q,  // User input passed directly
>       default_field: 'content',
>     },
>   },
> };
> ```
> Elasticsearch query_string parser can be exploited too. Someone could inject `field:* OR admin:true`.

**@security.chen** (10:20):
> This is P0. I'm creating a security incident. Both SQL and ES injection need to be fixed before we can consider this resolved.

---

**@dev.alex** (10:35):
> Found the index rebuild issue too. Customer reported that after we rebuilt their workspace index, some documents vanished:
> ```javascript
> async reindex() {
>   this.isReindexing = true;
>   try {
>     // Long-running operation
>     await rebuildIndex();
>   } finally {
>     this.isReindexing = false;
>   }
> }
> ```
> No lock during reindex. New documents created during rebuild don't get indexed.

**@sre.kim** (10:40):
> Confirmed. Their reindex ran from 02:00-02:45 UTC. They had 89 documents created during that window. All 89 are missing from search.

---

**@dev.marcus** (10:55):
> One more issue with multi-language content. Customer complaint:
> > "Our Japanese team's documents don't show up in search. Only English documents work."

**@dev.marcus** (10:58):
> Found it:
> ```javascript
> getTokenizer(language) {
>   // Always returns English tokenizer!
>   return 'standard';
> }
> ```
> We're ignoring the language parameter. Japanese needs kuromoji, Chinese needs smartcn, etc.

---

**@dev.sarah** (11:15):
> Also seeing permission filtering issues. Customer says they can see document snippets in search results for documents they don't have access to:
> ```javascript
> async searchWithPermissions(userId, params) {
>   // Fetches ALL results first
>   const results = await this.search(params);
>
>   // THEN filters by permission
>   const filtered = [];
>   for (const result of results.results) {
>     if (await this._checkPermission(userId, result.id)) {
>       filtered.push(result);
>     }
>   }
> }
> ```
> The search snippets are returned before filtering. Users see content they shouldn't have access to, even if the final list is filtered.

**@security.chen** (11:20):
> Adding this to the security incident. Information disclosure via search snippets.

---

## Summary of Issues

| Issue | Severity | Impact |
|-------|----------|--------|
| SQL Injection | Critical | Database compromise |
| ES Query Injection | High | Search manipulation |
| Indexing message loss | High | Documents not searchable |
| Autocomplete cache stale | Medium | Bad UX, old suggestions |
| Permission filtering race | High | Information disclosure |
| Index rebuild race | Medium | Missing documents after rebuild |
| Wrong tokenizer | Medium | Non-English search broken |
| Relevance scoring bug | Low | Ranking issues |

## Files to Investigate

- `services/search/src/services/search.js` - All search logic

---

**Action Items**:
- [ ] Fix SQL injection (P0)
- [ ] Fix ES injection (P0)
- [ ] Fix permission filtering race (P0)
- [ ] Add message acknowledgment after successful index (P1)
- [ ] Add cache TTL for autocomplete (P2)
- [ ] Add lock for reindex (P2)
- [ ] Fix tokenizer selection (P2)
