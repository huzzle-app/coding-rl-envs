# Slack Thread: Cache Inconsistencies and Strange Collection Errors

## #eng-backend - January 18, 2024

---

**@dev.rachel** (09:15):
> Hey team, anyone else seeing weird caching issues? I've got a customer reporting that when they rename a document, the old name keeps showing up randomly in different parts of the UI.

**@dev.tom** (09:22):
> Yeah, we've had a few tickets about that. I think there might be something wrong with our `@Cacheable` setup. Let me check the logs.

**@dev.rachel** (09:28):
> Found something interesting. We have two overloaded methods in DocumentService:
> ```java
> @Cacheable("documents")
> public Document getDocument(UUID id) { ... }
>
> @Cacheable("documents")
> public Document getDocument(UUID id, boolean includeVersions) { ... }
> ```
> Both use the same cache name but different parameters. Wouldn't that cause key collisions?

**@dev.tom** (09:35):
> Oh wow, you're right. The default cache key is based on parameter values, so `getDocument(uuid123)` and `getDocument(uuid123, true)` would have different keys... but wait, what about `getDocument(uuid123, false)` vs `getDocument(uuid123)`?

**@dev.rachel** (09:38):
> Actually I think the issue is different. Let me look at the key generation...

**@dev.rachel** (09:45):
> Found it! The default key generator uses all method parameters. So `getDocument(uuid123)` generates key `uuid123` but `getDocument(uuid123, false)` generates key `[uuid123, false]`. They're different keys, but they return different data for the same document. Then when we invalidate, we only invalidate one key.

**@dev.tom** (09:52):
> That explains the stale data. We need explicit cache keys or separate cache names.

---

**@dev.sarah** (10:05):
> Semi-related - I'm debugging a `ClassCastException` in SearchService. Check this out:
> ```
> java.lang.ClassCastException: class java.util.LinkedHashMap cannot be cast to class com.docuvault.model.Document
>     at com.docuvault.service.SearchService.searchDocuments(SearchService.java:89)
> ```

**@dev.tom** (10:12):
> That's weird. How would a LinkedHashMap get into a `List<Document>`?

**@dev.sarah** (10:18):
> I think I see it. There's a raw `List` being returned from a cache somewhere, and it's getting mixed with our generic `List<Document>`. Type erasure at runtime means the compiler can't catch it.
>
> ```java
> // Somewhere in SearchService
> List results = cacheManager.getResults(); // Raw type!
> List<Document> documents = results; // Compiles but unsafe
> for (Document doc : documents) { // ClassCastException at runtime
>     ...
> }
> ```

**@dev.rachel** (10:25):
> Found the actual code. It's worse:
> ```java
> @SuppressWarnings("unchecked")
> List<Document> cached = (List<Document>) cache.get(key);
> ```
> The cache is storing JSON-deserialized objects that come back as LinkedHashMaps, not Documents.

---

**@dev.mike** (10:45):
> Anyone know why we're getting `IllegalStateException: Duplicate key` errors in the document listing endpoint?
> ```
> java.lang.IllegalStateException: Duplicate key doc_12345
>     at java.util.stream.Collectors.duplicateKeyException(Collectors.java:135)
>     at com.docuvault.controller.DocumentController.listDocuments(DocumentController.java:78)
> ```

**@dev.sarah** (10:52):
> That's `Collectors.toMap()` - it throws when you try to add a duplicate key. We're probably not handling the case where the same document appears twice in the result set.

**@dev.mike** (10:58):
> Why would the same document appear twice?

**@dev.sarah** (11:05):
> Could be a JOIN that wasn't de-duplicated. Or maybe we're merging results from cache and database and getting duplicates. Either way, we need the merge function overload:
> ```java
> .collect(Collectors.toMap(
>     Document::getId,
>     Function.identity(),
>     (existing, replacement) -> existing  // merge function
> ))
> ```

---

**@dev.tom** (11:30):
> New fun one - `Iterator` issues in FileUtils:
> ```
> java.util.ConcurrentModificationException
>     at java.util.ArrayList$Itr.checkForComodification(ArrayList.java:1013)
>     at com.docuvault.util.FileUtils.cleanupTempFiles(FileUtils.java:145)
> ```

**@dev.rachel** (11:38):
> Let me guess - iterating over a list while removing elements from it?

**@dev.tom** (11:42):
> Exactly:
> ```java
> for (File file : tempFiles) {
>     if (file.isExpired()) {
>         tempFiles.remove(file);  // CME!
>     }
> }
> ```

**@dev.sarah** (11:48):
> Classic. Need to use `Iterator.remove()` or `removeIf()`.

---

**@dev.mike** (12:15):
> Wait, I found another caching issue. Our `@Async` methods aren't running asynchronously:
> ```java
> @Service
> public class DocumentService {
>     @Async
>     public CompletableFuture<Void> processDocumentAsync(UUID id) {
>         // This runs on the calling thread!
>     }
>
>     public void handleUpload(UUID id) {
>         this.processDocumentAsync(id);  // <-- Called via 'this'
>     }
> }
> ```

**@dev.rachel** (12:22):
> Same Spring proxy pitfall as `@Transactional`. Self-invocation bypasses the proxy. We see this a lot.

**@dev.tom** (12:28):
> How do we even test for this? The code "works" - it just runs synchronously instead of async.

**@dev.sarah** (12:35):
> We could check `Thread.currentThread().getName()` - async should run on a different thread pool. Or inject the service into itself with `@Lazy` and call through that reference.

---

**@dev.mike** (13:00):
> One more: Document's `hashCode()` is based on the mutable `name` field. I just saw documents disappear from a HashMap after being renamed:
> ```java
> Map<Document, List<Version>> docVersions = new HashMap<>();
> docVersions.put(document, versions);
> document.setName("new name");  // hashCode changes!
> docVersions.get(document);     // Returns null!
> ```

**@dev.rachel** (13:08):
> That's a nasty one. HashMap stores entries based on hashCode at insertion time. If hashCode changes, the entry is effectively lost.

**@dev.tom** (13:15):
> Should hashCode use only the immutable `id` field instead?

**@dev.sarah** (13:22):
> Yes, for JPA entities the standard practice is to use only the `id` (or business key) in `hashCode()` and `equals()`. Mutable fields are dangerous.

---

**@dev.rachel** (14:00):
> I also found that our subList usage is causing memory issues:
> ```java
> List<Document> allDocs = repository.findAll();  // 10,000 documents
> List<Document> page = allDocs.subList(0, 20);   // First 20
> return page;  // Retains reference to all 10,000!
> ```

**@dev.tom** (14:08):
> Right, `subList()` returns a view backed by the original list. We should wrap it:
> ```java
> return new ArrayList<>(allDocs.subList(0, 20));
> ```

---

**@dev.sarah** (14:30):
> Summary of issues to fix:
> 1. `@Cacheable` key collision on overloaded methods
> 2. Type erasure / raw List causing ClassCastException
> 3. `Collectors.toMap()` duplicate key not handled
> 4. Iterator modification during iteration
> 5. `@Async` self-invocation bypass
> 6. Mutable HashMap key (Document.hashCode using mutable field)
> 7. subList memory leak
>
> That's a lot of subtle Java/Spring gotchas in one codebase!

**@dev.tom** (14:38):
> Let's prioritize by customer impact. The cache inconsistency (1, 2) and HashMap key (6) issues are causing visible data corruption. Those should be first.

**@dev.rachel** (14:45):
> Agreed. I'll create tickets. Can someone run the full test suite to see what's failing? `mvn test` should surface most of these.

---

## Files to Investigate

Based on discussion:
- `src/main/java/com/docuvault/service/DocumentService.java` - @Cacheable, @Async issues
- `src/main/java/com/docuvault/service/SearchService.java` - Type erasure, subList
- `src/main/java/com/docuvault/controller/DocumentController.java` - Collectors.toMap
- `src/main/java/com/docuvault/model/Document.java` - hashCode/equals
- `src/main/java/com/docuvault/util/FileUtils.java` - Iterator modification
- `src/main/java/com/docuvault/service/ShareService.java` - Wildcard generics

---

**Action Items**:
- [ ] Add explicit cache keys to overloaded @Cacheable methods
- [ ] Fix raw type usage in SearchService
- [ ] Add merge function to Collectors.toMap calls
- [ ] Use Iterator.remove() or removeIf() in FileUtils
- [ ] Fix @Async self-invocation
- [ ] Update Document.hashCode to use only immutable id field
- [ ] Wrap subList results in new ArrayList
