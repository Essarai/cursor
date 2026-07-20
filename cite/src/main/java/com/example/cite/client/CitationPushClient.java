package com.example.cite.client;

import java.time.Duration;
import java.util.List;

import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import com.example.cite.config.CitationPushProperties;
import com.example.cite.entity.vo.CitationPushOutboxVo;
import com.example.cite.entity.vo.CitationPushResponseVo;

import lombok.extern.slf4j.Slf4j;

@Slf4j
@Component
public class CitationPushClient {

	private final CitationPushProperties properties;
	private final RestClient restClient;

	public CitationPushClient(CitationPushProperties properties, RestClient.Builder restClientBuilder) {
		this.properties = properties;
		SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
		factory.setConnectTimeout(Duration.ofMillis(properties.getConnectTimeout()));
		factory.setReadTimeout(Duration.ofMillis(properties.getReadTimeout()));
		this.restClient = restClientBuilder.requestFactory(factory).build();
	}

	public CitationPushResponseVo push(List<CitationPushOutboxVo> articles) {
		String url = properties.getUrl();
		if (url == null || url.isBlank()) {
			throw new IllegalStateException("cite.push.url 未配置");
		}
		log.debug("推送 {} 条到 {}", articles.size(), url);
		return restClient.post()
				.uri(url)
				.body(articles)
				.retrieve()
				.body(CitationPushResponseVo.class);
	}

}
