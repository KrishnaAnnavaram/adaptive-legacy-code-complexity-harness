package com.example.service;

import java.util.*;
import com.example.model.Circle;
import com.example.model.Color;
import com.example.model.Shape;

public class ShapeService extends AbstractService implements Runnable {

    private final List<Shape> shapes = new ArrayList<>();

    public void add(Shape shape) {
        shapes.add(shape);
    }

    public Circle makeRedCircle(double radius) {
        return new Circle(radius, Color.RED);
    }

    @Override
    public void run() {
        for (Shape shape : shapes) {
            System.out.println(shape.area());
        }
    }
}