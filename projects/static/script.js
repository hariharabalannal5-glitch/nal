const TIME_SLOTS = ['7AM-8AM', '8AM-9AM', '9AM-10AM', '10AM-11AM', '12PM-1PM', '2PM-3PM', '3PM-4PM', '4PM-5PM'];

const ROOM_NAMES = {
    '1': 'Auditorium',
    '2': 'Committee Room',
    '3': 'Conference Room'
};

let selectedRoom = null;
let currentDate = new Date();
let currentDayStart = new Date().getDate();  // ⭐ CHANGED: Start from today
let bookings = {};
let pendingBookings = new Set();
let userName = '';

document.addEventListener('DOMContentLoaded', function () {
    userName = document.querySelector('.user-info .badge')
        ?.textContent.replace('Room Booking for ', '') || '';

    // ✅ Initialize dropdowns to current date
    setDropdownToToday();
    loadBookings();

    document.querySelectorAll('.room-btn').forEach(btn => {
        btn.addEventListener('click', function (e) {
            // ⭐ UPDATED: Reset to today instead of day 1
            currentDate = new Date();          // reset date to today
            const today = new Date();
            currentDayStart = today.getDate(); // ⭐ start from today's day
            pendingBookings.clear();           // clear selections
            setDropdownToToday();              // reset dropdowns

            document.querySelectorAll('.room-btn')
                .forEach(b => b.classList.remove('selected'));

            e.target.classList.add('selected');
            selectedRoom = e.target.dataset.room;

            document.getElementById('selected-room').innerHTML =
                `✅ ${ROOM_NAMES[selectedRoom]} Selected`;

            document.getElementById('calendar-section').style.display = 'block';

            generateCalendar();
        });
    });

    // Dropdown listeners
    document.getElementById('month-select').addEventListener('change', updateFromDropdown);
    document.getElementById('year-select').addEventListener('change', updateFromDropdown);

    setupConfirmButton();
});

/* ---------------- HELPERS ---------------- */

function setDropdownToToday() {
    const today = new Date();
    document.getElementById('month-select').value = today.getMonth();
    document.getElementById('year-select').value = today.getFullYear();
}

function updateFromDropdown() {
    const month = parseInt(document.getElementById('month-select').value);
    const year = parseInt(document.getElementById('year-select').value);

    currentDate = new Date(year, month, 1);

    // ⭐ NEW: Logic for current month vs other months
    const today = new Date();
    if (year === today.getFullYear() && month === today.getMonth()) {
        // Current month => start from today
        currentDayStart = today.getDate();
    } else {
        // Other month => start from day 1
        currentDayStart = 1;
    }

    generateCalendar();
}

async function loadBookings() {
    try {
        const response = await fetch('/api/bookings');
        bookings = await response.json();
        if (selectedRoom) generateCalendar();
    } catch {
        bookings = {};
    }
}

function generateCalendar() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const endDay = Math.min(currentDayStart + 6, daysInMonth);

    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

    document.getElementById('day-range').textContent = `Days ${currentDayStart}-${endDay}`;

    let gridHTML = '<div class="date-header empty"></div>';

    for (let i = 0; i < 7; i++) {
        const day = currentDayStart + i;
        gridHTML += day <= daysInMonth
            ? `<div class="date-header">Day ${day}</div>`
            : `<div class="date-header empty"></div>`;
    }

    TIME_SLOTS.forEach((time, row) => {
        gridHTML += `<div class="time-slot">${time}</div>`;

        for (let i = 0; i < 7; i++) {
            const day = currentDayStart + i;

            if (day > daysInMonth) {
                gridHTML += `<div class="booking-cell disabled"></div>`;
                continue;
            }

            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            const cellId = `${selectedRoom}_${dateStr}_${row}`;
            const bookingData = bookings[cellId];

            if (dateStr < todayStr) {
                gridHTML += `<div class="booking-cell past">Past</div>`;
                continue;
            }

            if (bookingData) {
                const prevCellId = `${selectedRoom}_${dateStr}_${row - 1}`;
                const prevBooking = bookings[prevCellId];
                if (prevBooking && prevBooking.name === bookingData.name) continue;

                let span = 1, nextRow = row + 1;
                while (true) {
                    const nextCellId = `${selectedRoom}_${dateStr}_${nextRow}`;
                    const nextBooking = bookings[nextCellId];
                    if (nextBooking && nextBooking.name === bookingData.name) {
                        span++; nextRow++;
                    } else break;
                }

                const isOwner = userName.includes(bookingData.name);

                gridHTML += `
                    <div class="booking-cell booked ${isOwner ? 'owner-booked' : ''} merged-booking"
                         style="grid-row: span ${span}" data-cell="${cellId}">
                        ${ROOM_NAMES[selectedRoom]}<br>booked by<br>
                        <strong>DR. ${bookingData.name}</strong>
                        ${isOwner ? '<br><small>Click to Remove</small>' : ''}
                    </div>`;
            } else {
                const pending = pendingBookings.has(cellId);
                gridHTML += `
                    <div class="booking-cell ${pending ? 'pending' : ''}" data-cell="${cellId}">
                        ${pending ? 'Booking...' : 'Available'}
                    </div>`;
            }
        }
    });

    document.getElementById('calendar-grid').innerHTML = gridHTML;
    setupCellClicks();
    updatePagination(daysInMonth);
    updateConfirmButton();
}

function setupCellClicks() {
    document.querySelectorAll('.booking-cell:not(.booked):not(.disabled):not(.past)').forEach(cell => {
        cell.onclick = () => {
            const cellId = cell.dataset.cell;
            pendingBookings.has(cellId)
                ? pendingBookings.delete(cellId)
                : pendingBookings.add(cellId);
            generateCalendar();
        };
    });

    document.querySelectorAll('.booking-cell.owner-booked').forEach(cell => {
        cell.onclick = async () => {
            const cellId = cell.dataset.cell;
            if (!confirm('Remove your booking?')) return;

            const response = await fetch('/api/bookings', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cellId })
            });

            const result = await response.json();
            if (result.success) {
                await loadBookings();
                generateCalendar();
            } else alert(result.message);
        };
    });
}

function setupConfirmButton() {
    document.getElementById('confirm-booking').onclick = async function () {
        if (!pendingBookings.size) return;

        this.disabled = true;
        document.getElementById('booking-status').textContent = 'Booking...';

        const results = await Promise.all([...pendingBookings].map(cellId =>
            fetch('/api/bookings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cellId })
            }).then(r => r.json())
        ));

        if (results.every(r => r.success)) {
            pendingBookings.clear();
            await loadBookings();
            generateCalendar();
        } else alert('Some slots already booked');

        this.disabled = false;
    };
}

function updateConfirmButton() {
    const btn = document.getElementById('confirm-booking');
    const section = document.getElementById('confirm-section');

    if (!pendingBookings.size) {
        btn.disabled = true;
        section.style.display = 'none';
    } else {
        btn.disabled = false;
        btn.textContent = `Confirm ${pendingBookings.size} Slot(s)`;
        section.style.display = 'block';
    }
}

function updatePagination(daysInMonth) {
    document.getElementById('prev-days').onclick = () => {
        currentDayStart = Math.max(1, currentDayStart - 7);
        generateCalendar();
    };

    document.getElementById('next-days').onclick = () => {
        currentDayStart = Math.min(daysInMonth - 6, currentDayStart + 7);
        generateCalendar();
    };
}
