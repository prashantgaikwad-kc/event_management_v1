<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Button, call } from 'frappe-ui'
import { LineChart } from 'frappe-ui/charts'

interface EventOption {
  name: string
  event_name: string
}

interface Summary {
  registrations: { total: number; pending: number; confirmed: number; cancelled: number }
  tickets: { total_issued: number; issued: number; checked_in: number }
  attendance_percentage: number
}

interface TrendPoint {
  date: string | null
  count: number
}

interface CheckInRow {
  event: string
  attendee_name: string
  ticket_type: string
  status: string
  check_in_time: string | null
}

const emit = defineEmits<{ back: [] }>()
const events = ref<EventOption[]>([])
const selectedEvent = ref('')
const summary = ref<Summary | null>(null)
const trend = ref<TrendPoint[]>([])
const report = ref<CheckInRow[]>([])
const loading = ref(false)
const error = ref('')
let requestId = 0

const chartData = computed(() => trend.value
  .filter((point) => point.date))

async function loadDashboard() {
  const currentRequest = ++requestId
  loading.value = true
  error.value = ''
  summary.value = null
  trend.value = []
  report.value = []

  try {
    const args = selectedEvent.value ? { event: selectedEvent.value } : {}
    const [nextSummary, nextTrend, nextReport] = await Promise.all([
      call<Summary>('event_management.event_management.doctype.em_event.em_event.organizer_summary', args),
      call<TrendPoint[]>('event_management.event_management.doctype.em_event.em_event.organizer_registration_trend', args),
      call<CheckInRow[]>('event_management.event_management.doctype.em_event.em_event.organizer_check_in_report', args),
    ])
    if (currentRequest !== requestId) return
    summary.value = nextSummary
    trend.value = nextTrend
    report.value = nextReport
  } catch (cause) {
    if (currentRequest === requestId) {
      error.value = cause instanceof Error ? cause.message : 'Unable to load organizer dashboard.'
    }
  } finally {
    if (currentRequest === requestId) loading.value = false
  }
}

function exportAttendees() {
  const method = '/api/method/event_management.event_management.doctype.em_event.em_event.organizer_attendee_export'
  const url = selectedEvent.value ? `${method}?event=${encodeURIComponent(selectedEvent.value)}` : method
  window.location.assign(url)
}

watch(selectedEvent, loadDashboard)

onMounted(async () => {
  try {
    events.value = await call<EventOption[]>(
      'event_management.event_management.doctype.em_event.em_event.organizer_events',
    )
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Unable to load events.'
  }
  await loadDashboard()
})
</script>

<template>
  <div>
    <Button variant="subtle" @click="emit('back')">← Back</Button>
    <div class="page-header flex flex-wrap items-end justify-between gap-4">
      <div>
        <span class="eyebrow">EVENT INTELLIGENCE</span><h1 class="page-title">Organizer Dashboard</h1>
        <p class="page-subtitle">Registrations and attendance</p>
      </div>
      <div class="flex flex-wrap items-end gap-3">
        <label class="block text-sm font-medium">
          Event
          <select v-model="selectedEvent" class="field-input mt-1 block min-w-48">
            <option value="">All Events</option>
            <option v-for="event in events" :key="event.name" :value="event.name">
              {{ event.event_name }}
            </option>
          </select>
        </label>
        <Button variant="solid" @click="exportAttendees">Export CSV</Button>
      </div>
    </div>

    <p v-if="loading" class="mt-6">Loading dashboard...</p>
    <p v-if="error" class="feedback-error mt-6" role="alert">{{ error }}</p>

    <template v-if="!loading && !error && summary">
      <div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div v-for="item in [
          { label: 'Total Registrations', value: summary.registrations.total },
          { label: 'Pending Registrations', value: summary.registrations.pending },
          { label: 'Confirmed Registrations', value: summary.registrations.confirmed },
          { label: 'Cancelled Registrations', value: summary.registrations.cancelled },
          { label: 'Tickets Issued', value: summary.tickets.total_issued },
          { label: 'Checked-in Tickets', value: summary.tickets.checked_in },
          { label: 'Attendance Percentage', value: `${summary.attendance_percentage}%` },
        ]" :key="item.label" class="panel">
          <p class="text-sm text-gray-600">{{ item.label }}</p>
          <p class="metric-value mt-2">{{ item.value }}</p>
        </div>
      </div>

      <div class="panel mt-8">
        <div class="h-72">
          <LineChart title="Registration Trend" :data="chartData" x="date" y="count" :x-axis="{ type: 'category' }" />
        </div>
      </div>

      <div class="surface mt-8 overflow-hidden">
        <h3 class="p-5 text-lg font-semibold">Check-in Report</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-sm">
            <thead class="border-y bg-gray-50 text-gray-600">
              <tr>
                <th class="px-5 py-3">Event</th>
                <th class="px-5 py-3">Attendee Name</th>
                <th class="px-5 py-3">Ticket Type</th>
                <th class="px-5 py-3">Ticket Status</th>
                <th class="px-5 py-3">Check-in Time</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in report" :key="index" class="border-b last:border-b-0">
                <td class="px-5 py-3">{{ row.event }}</td>
                <td class="px-5 py-3">{{ row.attendee_name }}</td>
                <td class="px-5 py-3">{{ row.ticket_type }}</td>
                <td class="px-5 py-3">{{ row.status }}</td>
                <td class="px-5 py-3">{{ row.check_in_time || '—' }}</td>
              </tr>
              <tr v-if="!report.length"><td colspan="5" class="px-5 py-6 text-center text-gray-600">No tickets found.</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
