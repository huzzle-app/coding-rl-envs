package com.mindvault.shared.kotlin


typealias EventHandler = suspend (com.mindvault.shared.events.DomainEvent) -> Unit


inline class UserId(val value: String) 

@JvmInline
value class DocumentId(val value: String)

@JvmInline
value class NodeId(val value: String)
