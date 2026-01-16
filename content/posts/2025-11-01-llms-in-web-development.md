---
action_run_id: '19000626966'
cover:
  alt: ''
  image: ''
date: '2025-11-01'
generation_costs:
  content_generation: 0.00084705
  image_generation: 0.0
  slug_generation: 1.44e-05
  title_generation: 5.3849999999999994e-05
icon: ''
reading_time: 5 min read
sources:
- author: samrolken
  platform: hackernews
  quality_score: 0.7959999999999999
  url: https://github.com/samrolken/nokode
summary: An in-depth look at artificial intelligence, web development based on insights
  from the tech community.
tags:
- artificial-intelligence
- web-development
- databases
- performance
title: 'LLMs in Web Development: The Future of Coding?'
word_count: 902
---

> **Attribution:** This article was based on content by **@samrolken** on **GitHub**.  
> Original: https://github.com/samrolken/nokode

## Introduction

In recent years, the landscape of software development has been transformed by the advent of artificial intelligence (AI) and, more specifically, large language models (LLMs). These models, capable of understanding and generating human-like text, have sparked discussions around their potential to automate coding tasks. A recent experiment shared on Hacker News by user @samrolken showcases a web application that leverages an LLM to manage contact information without traditional coding structures. This raises a provocative question: **If LLMs can handle tasks that developers typically code, what is the future of programming?**

In this article, we will explore the implications of using LLMs in web development, particularly focusing on the experiment’s findings regarding performance and user experience. We will also discuss the current challenges and practical applications of LLMs in software development, aiming to provide tech professionals with insights into the evolving role of AI in coding.

### Key Takeaways

- LLMs can automate tasks traditionally handled by developers, such as data management and UI generation, but current performance issues hinder their widespread adoption.
- The experiment shows that while LLMs can handle the backend logic, they struggle with speed and consistency, leading to high operational costs.
- Understanding the balance between AI capabilities and developer roles is crucial for the future of software development.
- As AI inference times improve, the paradigm of coding may shift dramatically, prompting a reevaluation of programming practices and tools.

## The Experiment: LLMs in Action

The project detailed by @samrolken involved creating a contact manager where every HTTP request is processed through an LLM. The application utilized three primary tools: a database (SQLite), a web response generator (for HTML, JSON, and JavaScript), and an update memory feature for user feedback. This approach eliminates conventional web development components like routes, controllers, and business logic. Instead, the LLM is responsible for designing database schemas, generating user interfaces from URL paths, and adapting to user input in natural language.

### Performance Challenges

Despite the innovative approach, the experiment revealed significant performance drawbacks. Each request took between 30 to 60 seconds to complete, and the cost per request was approximately $0.05. Such delays are not viable for real-world applications where users expect instantaneous responses. Performance issues in LLMs can often be attributed to the complexity of natural language processing tasks, which require substantial computational resources (Brown et al., 2020). 

Furthermore, the inconsistency in user interface design across requests raises questions about user experience. A web application that presents a different layout or functionality on each interaction would likely frustrate users and undermine trust in the application. These challenges highlight the gap between the theoretical capabilities of LLMs and their practical application in software development.

### The Role of AI in Software Development

The integration of AI in software development is not a new concept, but the rise of LLMs has introduced a paradigm shift. Traditionally, developers write code to define logic, manage data flow, and create user interfaces. However, as LLM technology matures, it is becoming increasingly capable of performing these tasks with minimal human intervention. 

Research by Vaswani et al. (2017) on the Transformer architecture, which underpins many current LLMs, illustrates how these models can be trained on vast datasets to understand context and generate coherent text. This capability has led to the development of tools that assist developers by automating mundane tasks, such as code completion and bug detection. However, the question remains: Can LLMs fully replace traditional coding practices?

### Practical Implications for Developers

For tech professionals, the findings from the contact manager experiment serve as both a warning and an opportunity. While the potential for LLMs to handle coding tasks is exciting, the current performance limitations suggest that they are not yet ready to replace developers entirely. Instead, developers might consider integrating LLMs into their workflows to enhance productivity rather than replace their roles.

For instance, LLMs can be employed for rapid prototyping or to generate boilerplate code, allowing developers to focus on more complex tasks. Moreover, as performance improves, LLMs could serve as powerful tools for generating documentation, writing tests, or even assisting in debugging processes.

However, ethical considerations must also be addressed. The reliance on AI for coding raises questions about accountability for errors and the potential displacement of jobs. As the technology continues to evolve, it will be essential for the industry to develop frameworks that ensure ethical AI use, balancing efficiency with human oversight.

## Conclusion

The experiment conducted by @samrolken provides a fascinating glimpse into the future of software development, where LLMs could take on tasks traditionally handled by developers. While the technology shows promise, significant challenges remain—most notably in performance and consistency. As we move forward, the focus should not only be on how to utilize LLMs for code generation but also on understanding their limitations and integrating them thoughtfully into existing workflows.

As LLM inference speeds improve and operational costs decrease, we may witness a fundamental shift in the role of programming in the tech industry. Developers should stay informed about these advancements and be prepared to adapt their skill sets accordingly. The future of coding may not be about writing lines of code but rather about orchestrating intelligent systems to solve complex problems.

### Source Attribution

This article is based on an original post by @samrolken on Hacker News, detailing an experiment using LLMs in web application development. For further details, you can access the source [here](https://github.com/samrolken/nokode).

## References

- [Show HN: Why write code if the LLM can just do the thing? (web app experiment)](https://github.com/samrolken/nokode) — @samrolken on GitHub