package com.example.cite;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;

import com.example.cite.repository.CitationPushOutboxRepository;

@SpringBootTest
class CiteApplicationTests {

	@MockBean
	private CitationPushOutboxRepository citationPushOutboxRepository;

	@Test
	void contextLoads() {
	}

}
