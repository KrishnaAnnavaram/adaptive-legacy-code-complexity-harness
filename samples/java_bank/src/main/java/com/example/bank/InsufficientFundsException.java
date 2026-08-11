package com.example.bank;

/** Domain exception. Extends an external type (java.lang.RuntimeException). */
public class InsufficientFundsException extends RuntimeException {

    public InsufficientFundsException(String message) {
        super(message);
    }
}
