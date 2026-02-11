namespace HealthLink.Api.Models;

public class Patient
{
    public int Id { get; set; }

    public string Name { get; set; } = null!;

    public string? NormalizedName { get; set; }

    public string Email { get; set; } = null!;
    public DateTime DateOfBirth { get; set; }
    public bool IsActive { get; set; } = true;
    public Address? Address { get; set; }

    public List<Appointment> Appointments { get; set; } = new();
    public List<PatientDocument> Documents { get; set; } = new();
}

public class Address
{
    public string Street { get; set; } = "";
    public string City { get; set; } = "";
    public string State { get; set; } = "";
    public string ZipCode { get; set; } = "";
}

public class PatientDocument
{
    public int Id { get; set; }
    public int PatientId { get; set; }
    public string FileName { get; set; } = "";
    public string ContentType { get; set; } = "";
    public long FileSize { get; set; }
    public DateTime UploadDate { get; set; }

    public Patient Patient { get; set; } = null!;
}
