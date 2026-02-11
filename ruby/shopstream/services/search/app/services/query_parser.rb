# frozen_string_literal: true

class QueryParser
  

  
  # on certain inputs like "aaaaaaaaaaaaaaaaaaaaaaaaaaa!"
  WORD_PATTERN = /(\w+\s*)+/

  
  QUOTED_STRING_PATTERN = /(["'])(?:(?!\1)[^\\]|\\.)*\1/

  
  FILTER_PATTERN = /(\w+):((?:[^"\s]+)|(?:"[^"]*"))+/

  def parse(query)
    
    tokens = tokenize(query)

    {
      terms: extract_terms(tokens),
      filters: extract_filters(tokens),
      phrases: extract_phrases(tokens)
    }
  end

  def tokenize(query)
    tokens = []

    
    # Input like "a]a]a]a]a]a]a]a]a]a]" causes ReDoS
    scanner = StringScanner.new(query)

    until scanner.eos?
      if scanner.scan(QUOTED_STRING_PATTERN)
        tokens << { type: :phrase, value: scanner.matched }
      elsif scanner.scan(FILTER_PATTERN)
        tokens << { type: :filter, value: scanner.matched }
      elsif scanner.scan(/\S+/)
        tokens << { type: :term, value: scanner.matched }
      else
        scanner.getch
      end
    end

    tokens
  end

  def validate_query(query)
    
    return false if query.length > 1000

    
    unless query.match?(/^[\w\s"':.-]+$/)
      return false
    end

    
    balanced = query.match?(/^([^"]*"[^"]*")*[^"]*$/)

    balanced
  end

  def highlight_matches(text, query)
    
    terms = query.split(/\s+/)

    
    # Malicious term like "(a+)+" causes ReDoS
    pattern = terms.map { |t| Regexp.escape(t) }.join('|')

    
    text.gsub(/(#{pattern})/i, '<mark>\1</mark>')
  end

  private

  def extract_terms(tokens)
    tokens.select { |t| t[:type] == :term }.map { |t| t[:value] }
  end

  def extract_filters(tokens)
    filters = {}
    tokens.select { |t| t[:type] == :filter }.each do |token|
      key, value = token[:value].split(':', 2)
      filters[key] = value.gsub('"', '')
    end
    filters
  end

  def extract_phrases(tokens)
    tokens.select { |t| t[:type] == :phrase }.map { |t| t[:value].gsub('"', '') }
  end
end

# Correct implementation:
# class QueryParser
#   MAX_QUERY_LENGTH = 500
#   MAX_TOKENS = 50
#
#   # Use atomic groups and possessive quantifiers where possible
#   # Or avoid complex regex entirely
#
#   def parse(query)
#     return empty_result if query.blank?
#     return empty_result if query.length > MAX_QUERY_LENGTH
#
#     # Simple tokenization without complex regex
#     tokens = simple_tokenize(query)
#     tokens = tokens.first(MAX_TOKENS)
#
#     {
#       terms: tokens.select { |t| t[:type] == :term },
#       filters: tokens.select { |t| t[:type] == :filter },
#       phrases: tokens.select { |t| t[:type] == :phrase }
#     }
#   end
#
#   def simple_tokenize(query)
#     tokens = []
#     in_quote = false
#     current = ''
#
#     query.each_char do |char|
#       case char
#       when '"'
#         if in_quote
#           tokens << { type: :phrase, value: current }
#           current = ''
#         end
#         in_quote = !in_quote
#       when ' '
#         unless in_quote
#           process_token(current, tokens) if current.present?
#           current = ''
#         else
#           current += char
#         end
#       else
#         current += char
#       end
#     end
#
#     process_token(current, tokens) if current.present?
#     tokens
#   end
#
#   def highlight_matches(text, query)
#     # Limit highlighting to prevent ReDoS
#     terms = query.split(/\s+/).first(10)
#     terms = terms.select { |t| t.length >= 2 && t.length <= 50 }
#
#     result = text.dup
#     terms.each do |term|
#       escaped = Regexp.escape(term)
#       result.gsub!(/\b(#{escaped})\b/i, '<mark>\1</mark>')
#     end
#     result
#   end
# end
