# GitHub Issue: Audit event data structure against real-world event schemas

## Problem

We need to ensure our current event data structure captures all relevant information that's commonly available in real-world event listings. Our schema may be missing important fields that users expect or that would improve the user experience.

## Current Event Schema

Our current event structure includes:
- `source_id`: int|null
- `external_id`: string  
- `title`: string
- `description`: string
- `location`: string
- `start_time`: ISO datetime
- `end_time`: ISO datetime|null
- `url`: string|null

## Proposed Research

1. **Survey Popular Event Platforms:**
   - Eventbrite, Facebook Events, Meetup
   - Google Events, Apple Calendar
   - Local government event systems (Boston.gov, Cambridge, etc.)
   - Library systems (BPL, Needham Library, etc.)

2. **Analyze Schema.org Event Standards:**
   - Review [Schema.org Event](https://schema.org/Event) specification
   - Check JSON-LD event examples from real sites
   - Identify commonly used optional fields

3. **Common Missing Fields to Investigate:**
   - **Cost/Price information** (free, paid, price ranges)
   - **Event categories/tags** (workshop, lecture, concert, etc.)
   - **Organizer information** (name, contact, organization)
   - **Registration requirements** (required, optional, walk-in)
   - **Capacity/attendance limits**
   - **Accessibility information**
   - **Age restrictions** (all ages, 18+, family-friendly)
   - **Virtual/hybrid event details** (Zoom links, streaming info)
   - **Recurring event patterns** (daily, weekly, monthly)
   - **Image/media attachments**
   - **Contact information** (phone, email)

## Expected Outcomes

1. **Updated schema** that captures more comprehensive event data
2. **Updated scraper logic** to extract new fields
3. **API endpoint updates** to serve additional data

## Acceptance Criteria

- [ ] Research completed on 10+ major event platforms
- [ ] Gap analysis document comparing our schema vs industry standards
- [ ] Proposed new schema with rationale for each field
- [ ] Impact assessment on existing scrapers and API
- [ ] Implementation plan with phases/priorities

## Priority

Medium - This will improve data quality and user experience, but current schema works for basic functionality.