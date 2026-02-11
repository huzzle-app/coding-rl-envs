package com.docuvault.service;

import com.docuvault.model.Document;
import com.docuvault.model.User;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.config.ConfigurableBeanFactory;
import org.springframework.context.annotation.Scope;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Consumer;

@Service

// Category: Spring Framework
// NotificationService is declared as SCOPE_PROTOTYPE, meaning Spring should create
// a new instance for each injection point. However, when injected into singleton-scoped
// beans (DocumentService, ShareService) via @Autowired, the injection happens only once
// at singleton creation time. Every subsequent call uses the same instance, defeating
// the purpose of prototype scope. The instanceId field is the same across all usages.
// Fix: Use @Scope(value = SCOPE_PROTOTYPE, proxyMode = ScopedProxyMode.TARGET_CLASS)
// to create a scoped proxy, or inject via ObjectProvider<NotificationService>
// and call objectProvider.getObject() each time a new instance is needed
@Scope(ConfigurableBeanFactory.SCOPE_PROTOTYPE)
public class NotificationService {

    private static final Logger log = LoggerFactory.getLogger(NotificationService.class);

    private final String instanceId = java.util.UUID.randomUUID().toString().substring(0, 8);

    
    // Category: Concurrency
    // Multiple threads can concurrently call addListener() (which modifies the list)
    // while another thread is inside notifyDocumentCreated() (which iterates the list).
    // The for-each loop uses an Iterator that checks for structural modification;
    // a concurrent add() sets the modCount, causing the iterator to throw
    // ConcurrentModificationException on the next iteration step.
    // Fix: Use CopyOnWriteArrayList instead of ArrayList, or synchronize all
    // access to the listeners list with a shared lock object
    private final List<Consumer<Document>> listeners = new ArrayList<>();

    @Autowired
    private DocumentService documentService;

    public String getInstanceId() {
        return instanceId;
    }

    public void addListener(Consumer<Document> listener) {
        
        // ConcurrentModificationException in notifyDocumentCreated()
        listeners.add(listener);
    }

    public void removeListener(Consumer<Document> listener) {
        listeners.remove(listener);
    }

    public void notifyDocumentCreated(Document document) {
        log.info("[{}] Notifying {} listeners of document creation: {}",
            instanceId, listeners.size(), document.getName());

        
        // If addListener() is called concurrently by another thread during this
        // iteration, the ArrayList's internal modCount changes, and the iterator's
        // expectedModCount check fails, throwing ConcurrentModificationException
        for (Consumer<Document> listener : listeners) {
            try {
                listener.accept(document);
            } catch (Exception e) {
                log.error("Listener error", e);
            }
        }
    }

    public void notifyDocumentShared(Document document, User targetUser) {
        log.info("[{}] Notifying document shared: {} with user: {}",
            instanceId, document.getName(), targetUser.getUsername());
    }

    public void notifyDocumentDeleted(Document document) {
        log.info("[{}] Notifying document deleted: {}", instanceId, document.getName());
        
        // this loop causes ConcurrentModificationException
        for (Consumer<Document> listener : listeners) {
            try {
                listener.accept(document);
            } catch (Exception e) {
                log.error("Listener error", e);
            }
        }
    }

    public int getListenerCount() {
        return listeners.size();
    }
}
