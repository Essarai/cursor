package com.example.cite.controller;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.example.cite.service.CitationPushService;
import com.example.cite.service.dto.CitationPushRunResult;

import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/citation-push")
@RequiredArgsConstructor
public class CitationPushController {

	private final CitationPushService pushService;

	@GetMapping("/stats")
	public Map<String, Long> stats() {
		return Map.of("remaining", pushService.countRemaining());
	}

	@PostMapping("/run")
	public CitationPushRunResult run(@RequestParam(defaultValue = "1") int batches) {
		return pushService.pushBatches(batches);
	}

}
