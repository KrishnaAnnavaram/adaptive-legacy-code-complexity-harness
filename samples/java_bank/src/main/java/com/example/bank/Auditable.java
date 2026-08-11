package com.example.bank;

/** Anything that can record an audit-trail entry. Implemented by Account. */
public interface Auditable {
    void audit(String event);
}
