package com.example.cite;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@EnableScheduling
@SpringBootApplication
public class CiteApplication {

	public static void main(String[] args) {
		SpringApplication.run(CiteApplication.class, args);
	}

}
