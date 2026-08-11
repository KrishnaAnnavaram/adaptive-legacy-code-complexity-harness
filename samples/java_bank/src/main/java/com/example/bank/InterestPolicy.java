package com.example.bank;

/** How interest accrues. Exercises an interface with a default method body. */
public interface InterestPolicy {

    double rate(int month);

    default double annualRate() {
        double sum = 0;
        for (int month = 1; month <= 12; month++) {
            sum += rate(month);
        }
        return sum;
    }
}
